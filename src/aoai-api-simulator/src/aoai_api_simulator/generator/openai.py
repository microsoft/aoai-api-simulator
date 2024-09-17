import asyncio
import json
import logging
import random
import time
from typing import Tuple

import nanoid
from aoai_api_simulator import constants
from aoai_api_simulator.auth import validate_api_key_header
from aoai_api_simulator.constants import (
    SIMULATOR_KEY_DEPLOYMENT_NAME,
    SIMULATOR_KEY_LIMITER,
    SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS,
    SIMULATOR_KEY_OPENAI_MAX_TOKENS_EFFECTIVE,
    SIMULATOR_KEY_OPENAI_MAX_TOKENS_REQUESTED,
    SIMULATOR_KEY_OPENAI_PROMPT_TOKENS,
    SIMULATOR_KEY_OPENAI_TOTAL_TOKENS,
    SIMULATOR_KEY_OPERATION_NAME,
)
from aoai_api_simulator.generator.openai_tokens import (
    get_max_completion_tokens,
    num_tokens_from_messages,
    num_tokens_from_string,
)
from aoai_api_simulator.models import OpenAIDeployment, RequestContext
from fastapi import Response
from fastapi.responses import StreamingResponse

# This file contains a default implementation of the openai generators
# You can configure your own generators by creating a generator_config.py file and setting the
# EXTENSION_PATH environment variable to the path of the file when running the API
# See examples/generator_echo for an example of how to define your own generators

logger = logging.getLogger(__name__)

# API docs: https://learn.microsoft.com/en-gb/azure/ai-services/openai/reference

missing_deployment_names = set()
missing_embedding_deployment_names = set()
default_openai_embedding_model = OpenAIDeployment(
    name="embedding", model="text-embedding-ada-002", tokens_per_minute=10000, embedding_size=1536
)


def get_embedding_model_from_deployment_name(context: RequestContext, deployment_name: str) -> OpenAIDeployment | None:
    """
    Gets the model name for the specified embedding deployment. If
    the deployment is not in the configured deployments then the
    default model is returned and a warning is logged.

    Args:
        context: RequestContext instance
        deployment_name: Name of the deployment

    Returns:
        OpenAIDeployment | None: Instance of OpenAIDeployment
    """
    deployments = context.config.openai_deployments

    if deployments:
        deployment = deployments.get(deployment_name)

        if deployment:
            return deployment

    if context.config.allow_undefined_openai_deployments:
        default_model_name = "embedding"

        # Output warning for missing embedding deployment name (only the
        # first time we encounter it)
        if deployment_name not in missing_embedding_deployment_names:
            missing_embedding_deployment_names.add(default_model_name)
            logger.warning(
                "Deployment %s not found in config and "
                "allow_undefined_openai_deployments is True. "
                "Using default model %s",
                deployment_name,
                default_model_name,
            )
        return default_openai_embedding_model

    # Output warning for missing embedding deployment name
    # (only the first time we encounter it)
    if deployment_name not in missing_deployment_names:
        missing_deployment_names.add(deployment_name)
        logger.warning(
            "Deployment %s not found in config and allow_undefined_openai_deployments is False", deployment_name
        )
    return None


def get_model_name_from_deployment_name(context: RequestContext, deployment_name: str) -> str | None:
    """
    Gets the model name for the specified deployment.
    If the deployment is not in the configured deployments then either a default model is returned (if )
    """
    deployments = context.config.openai_deployments
    if deployments:
        deployment = deployments.get(deployment_name)
        if deployment:
            return deployment.model

    if context.config.allow_undefined_openai_deployments:
        default_model = "gpt-3.5-turbo-0613"

        # Output warning for missing deployment name (only the first time we encounter it)
        if deployment_name not in missing_deployment_names:
            missing_deployment_names.add(deployment_name)
            logger.warning(
                "Deployment %s not found in config and allow_undefined_openai_deployments is True."
                + " Using default model %s",
                deployment_name,
                default_model,
            )
        return default_model

    # Output warning for missing deployment name (only the first time we encounter it)
    if deployment_name not in missing_deployment_names:
        missing_deployment_names.add(deployment_name)
        logger.warning(
            "Deployment %s not found in config and allow_undefined_openai_deployments is False", deployment_name
        )
    return None


async def calculate_latency(context: RequestContext, status_code: int):
    """Calculate additional latency that should be applied"""
    if status_code >= 300:
        return

    # Determine the target latency for the request
    completion_tokens = context.values.get(constants.SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS)

    if completion_tokens and completion_tokens > 0:
        config = context.config
        operation_name = context.values.get(constants.SIMULATOR_KEY_OPERATION_NAME)
        target_duration_ms = None
        if operation_name == "embeddings":
            # embeddings config returns latency value to use (in milliseconds)
            target_duration_ms = config.latency.open_ai_embeddings.get_value()
        elif operation_name == "completions":
            # completions config returns latency per completion token in milliseconds
            target_duration_ms = config.latency.open_ai_completions.get_value()
        elif operation_name == "chat-completions":
            # chat completions config returns latency per completion token in milliseconds
            target_duration_ms = config.latency.open_ai_chat_completions.get_value() * completion_tokens

        if target_duration_ms:
            context.values[constants.TARGET_DURATION_MS] = target_duration_ms


def create_embedding_content(index: int, embedding_size):
    """Generates a random embedding"""
    return {
        "object": "embedding",
        "index": index,
        "embedding": [(random.random() - 0.5) * 4 for _ in range(embedding_size)],
    }


def create_embeddings_response(
    context: RequestContext,
    deployment_name: str,
    deployment: OpenAIDeployment,
    request_input: str | list,
):
    embeddings = []
    if isinstance(request_input, str):
        tokens = num_tokens_from_string(request_input, deployment.model)
        embeddings.append(create_embedding_content(0, embedding_size=deployment.embedding_size))
    else:
        tokens = 0
        index = 0
        for i in request_input:
            tokens += num_tokens_from_string(i, deployment.model)
            embeddings.append(create_embedding_content(index, embedding_size=deployment.embedding_size))
            index += 1

    response_data = {
        "object": "list",
        "data": embeddings,
        "model": deployment.model,
        "usage": {"prompt_tokens": tokens, "total_tokens": tokens},
    }

    # store values in the context for use by the rate-limiter etc
    context.values[SIMULATOR_KEY_LIMITER] = "openai"
    context.values[SIMULATOR_KEY_OPERATION_NAME] = "embeddings"
    context.values[SIMULATOR_KEY_DEPLOYMENT_NAME] = deployment_name
    context.values[SIMULATOR_KEY_OPENAI_PROMPT_TOKENS] = tokens
    context.values[SIMULATOR_KEY_OPENAI_TOTAL_TOKENS] = tokens

    return Response(
        status_code=200,
        content=json.dumps(response_data),
        headers={
            "Content-Type": "application/json",
        },
    )


def get_lorem_factor(max_tokens: int):
    # Use a sliding factor for the number of words to generate based on the max_tokens
    if max_tokens > 500:
        return 0.72
    if max_tokens > 100:
        return 0.6
    return 0.5


# pylint: disable-next=too-few-public-methods
class LoremReference:
    """
    Generating large amounts of lorem text can be slow, so we pre-generate a set of reference values.
    These are then combined to generate the required amount of text for API requests
    """

    model_name: str
    values: dict[int, list[str]]
    token_sizes: list[int]

    def __init__(self, model_name: str, reference_values: dict[int, list[str]]):
        self.model_name = model_name
        self.values = reference_values
        self.token_sizes = sorted(reference_values.keys(), reverse=True)

    def get_value_for_size(self, size: int) -> Tuple[str, int] | None:
        for token_size in self.token_sizes:
            if token_size <= size:
                values = self.values[token_size]
                value = random.choice(values)
                return (value, token_size)
        return None


lorem_reference_values: dict[str, LoremReference] = {}


def generate_lorem_reference_text_values(token_values: list[int], model_name: str):
    value_count = 5  # number of reference values of each size to generate
    values = {}
    for max_tokens in token_values:
        generated_texts = [raw_generate_lorem_text(max_tokens, model_name) for _ in range(value_count)]
        values[max_tokens] = generated_texts

    return LoremReference(model_name, values)


def generate_lorem_text(max_tokens: int, model_name: str):
    text = ""
    target = max_tokens

    if model_name not in lorem_reference_values:
        logger.info("Generating lorem reference values for model %s...", model_name)
        start_time = time.perf_counter()
        token_sizes = [2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 4000]
        lorem_reference_values[model_name] = generate_lorem_reference_text_values(token_sizes, model_name)
        duration = time.perf_counter() - start_time
        logger.info("Generated lorem reference values for model %s (took %ss)", model_name, duration)
    reference_values = lorem_reference_values[model_name]

    separator = ""
    while target > 0:
        value = reference_values.get_value_for_size(target)
        if value is None:
            break
        new_text, size = value
        text += separator + new_text
        separator = " "
        target -= size

    while num_tokens_from_string(text, model_name) > max_tokens:
        # remove last word
        last_space = text.rfind(" ")
        text = text[:last_space]

    return text


lorem_words = [
    "ullamco",
    "labore",
    "cupidatat",
    "ipsum",
    "elit,",
    "esse",
    "officia",
    "aliquip",
    "do",
    "magna",
    "duis",
    "consequat",
    "exercitation",
    "occaecat",
    "ea",
    "laboris",
    "sit",
    "reprehenderit",
    "velit",
    "dolor",
    "enim",
    "irure",
    "anim",
    "nisi",
    "amet,",
    "culpa",
    "commodo",
    "consectetur",
    "eiusmod",
    "minim",
    "mollit",
    "fugiat",
    "cillum",
    "non",
    "deserunt",
    "veniam,",
    "est",
    "eu",
    "qui",
    "tempor",
    "adipiscing",
    "aliqua",
    "et",
    "nostrud",
    "ex",
    "incididunt",
    "aute",
    "nulla",
    "in",
    "proident,",
    "sunt",
    "id",
    "lorem",
    "pariatur",
    "excepteur",
    "ut",
    "ad",
    "sed",
    "sint",
    "laborum",
    "voluptate",
    "dolore",
    "quis",
]


def raw_lorem_get_word(count: int = 1) -> str:
    return " ".join([random.choice(lorem_words) for _ in range(count)])


def raw_generate_lorem_text(max_tokens: int, model_name: str) -> str:
    # The simplest approach to generating the compltion would
    # be to add a word at a time and count the tokens until we reach the limit
    # For large max_token values that will be slow, so we
    # estimate the number of words to generate based on the max_tokens
    # and then measure the number of tokens in that text
    # Then we repeat for the remaining token count
    # (allowing for some degree of error as tokens don't exactly combine that way )
    target = max_tokens
    full_text = ""
    sep = ""
    while target > 5:
        factor = get_lorem_factor(target)
        init_word_count = int(factor * target)
        # text = lorem.get_word(count=init_word_count)
        text = raw_lorem_get_word(count=init_word_count)
        used = num_tokens_from_string(text, model_name)
        if used > target:
            break
        full_text += sep + text
        sep = " "
        target -= used
        target -= 2  # allow for space and error margin in token count addition

    # Now top up the text to the max_tokens
    # by adding a word at a time
    while True:
        new_text = full_text + " " + raw_lorem_get_word()  # lorem.get_word()
        if num_tokens_from_string(new_text, model_name) > max_tokens:
            break
        full_text = new_text

    return full_text


def create_translation_response(
    context: RequestContext, response_format: str, deployment_name: str, model_name: str, max_tokens: int
):
    """
    Creates a Response object for a translation request and sets context values for the rate-limiter etc
    """
    text = generate_lorem_text(max_tokens=max_tokens, model_name=model_name)

    completion_tokens = num_tokens_from_string(text, model_name)

    if response_format == "text":
        return Response(
            content=text,
            headers={
                "Content-Type": "text/plain",
            },
            status_code=200,
        )
    return Response(
        content=json.dumps({"text": text}),
        headers={
            "Content-Type": "application/json",
        },
        status_code=200,
    )


def create_completion_response(
    context: RequestContext,
    deployment_name: str,
    model_name: str,
    prompt_tokens: int,
    max_tokens: int,
):
    """
    Creates a Response object for a completion request and sets context values for the rate-limiter etc
    """
    text = generate_lorem_text(max_tokens=max_tokens, model_name=model_name)

    completion_tokens = num_tokens_from_string(text, model_name)
    total_tokens = prompt_tokens + completion_tokens

    response_body = {
        "id": "cmpl-" + nanoid.non_secure_generate(size=29),
        "object": "text_completion",
        "created": int(time.time()),
        "model": model_name,
        "choices": [
            {
                "text": text,
                "index": 0,
                "finish_reason": "length",
                "logprobs": None,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    }

    # store values in the context for use by the rate-limiter etc
    context.values[SIMULATOR_KEY_LIMITER] = "openai"
    context.values[SIMULATOR_KEY_OPERATION_NAME] = "completions"
    context.values[SIMULATOR_KEY_DEPLOYMENT_NAME] = deployment_name
    context.values[SIMULATOR_KEY_OPENAI_PROMPT_TOKENS] = prompt_tokens
    context.values[SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS] = completion_tokens
    context.values[SIMULATOR_KEY_OPENAI_TOTAL_TOKENS] = total_tokens

    return Response(
        content=json.dumps(response_body),
        headers={
            "Content-Type": "application/json",
        },
        status_code=200,
    )


# pylint: disable-next=too-many-arguments
def create_lorem_chat_completion_response(
    context: RequestContext,
    deployment_name: str,
    model_name: str,
    streaming: bool,
    max_tokens: int,
    prompt_messages: list,
    finish_reason: str = "length",
):
    """
    Creates a Response object for a chat completion request by generating
    lorem ipsum text and sets context values for the rate-limiter etc.
    Handles streaming vs non-streaming
    """

    text = generate_lorem_text(max_tokens=max_tokens, model_name=model_name)

    return create_chat_completion_response(
        context=context,
        deployment_name=deployment_name,
        model_name=model_name,
        streaming=streaming,
        prompt_messages=prompt_messages,
        generated_content=text,
        finish_reason=finish_reason,
    )


# pylint: disable-next=too-many-arguments
def create_chat_completion_response(
    context: RequestContext,
    deployment_name: str,
    model_name: str,
    streaming: bool,
    prompt_messages: list,
    generated_content: str,
    finish_reason: str = "length",
):
    """
    Creates a Response object for a chat completion request and sets context values for the rate-limiter etc.
    Handles streaming vs non-streaming
    """

    prompt_tokens = num_tokens_from_messages(prompt_messages, model_name)

    text = "".join(generated_content)
    completion_tokens = num_tokens_from_string(text, model_name)
    total_tokens = prompt_tokens + completion_tokens

    # store values in the context for use by the rate-limiter etc
    context.values[SIMULATOR_KEY_LIMITER] = "openai"
    context.values[SIMULATOR_KEY_OPERATION_NAME] = "chat-completions"
    context.values[SIMULATOR_KEY_DEPLOYMENT_NAME] = deployment_name
    context.values[SIMULATOR_KEY_OPENAI_PROMPT_TOKENS] = prompt_tokens
    context.values[SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS] = completion_tokens
    context.values[SIMULATOR_KEY_OPENAI_TOTAL_TOKENS] = total_tokens

    if streaming:

        async def send_words():
            space = ""
            role = "assistant"
            for word in generated_content.split(" "):
                chunk_string = json.dumps(
                    {
                        "id": "chatcmpl-" + nanoid.non_secure_generate(size=29),
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model_name": model_name,
                        "system_fingerprint": None,
                        "choices": [
                            {
                                "delta": {
                                    "content": space + word,
                                    "function_call": None,
                                    "role": role,
                                    "tool_calls": None,
                                    "finish_reason": None,
                                    "index": 0,
                                    "logprobs": None,
                                    "content_filter_results": {
                                        "hate": {"filtered": False, "severity": "safe"},
                                        "self_harm": {"filtered": False, "severity": "safe"},
                                        "sexual": {"filtered": False, "severity": "safe"},
                                        "violence": {"filtered": False, "severity": "safe"},
                                    },
                                },
                            },
                        ],
                    }
                )
                role = None

                yield "data: " + chunk_string + "\n"
                yield "\n"
                await asyncio.sleep(0.05)
                space = " "

            chunk_string = json.dumps(
                {
                    "id": "chatcmpl-" + nanoid.non_secure_generate(size=29),
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model_name": model_name,
                    "system_fingerprint": None,
                    "choices": [
                        {
                            "delta": {
                                "content": None,
                                "function_call": None,
                                "role": None,
                                "tool_calls": None,
                                "finish_reason": finish_reason,
                                "index": 0,
                                "logprobs": None,
                                "content_filter_results": {
                                    "hate": {"filtered": False, "severity": "safe"},
                                    "self_harm": {"filtered": False, "severity": "safe"},
                                    "sexual": {"filtered": False, "severity": "safe"},
                                    "violence": {"filtered": False, "severity": "safe"},
                                },
                            },
                        },
                    ],
                }
            )

            yield "data: " + chunk_string + "\n"
            yield "\n"
            yield "[DONE]"

        return StreamingResponse(content=send_words())

    response_body = {
        "id": "chatcmpl-" + nanoid.non_secure_generate(size=29),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
        "prompt_filter_results": [
            {
                "prompt_index": 0,
                "content_filter_results": {
                    "hate": {"filtered": False, "severity": "safe"},
                    "self_harm": {"filtered": False, "severity": "safe"},
                    "sexual": {"filtered": False, "severity": "safe"},
                    "violence": {"filtered": False, "severity": "safe"},
                },
            }
        ],
        "choices": [
            {
                "finish_reason": finish_reason,
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text,
                },
                "content_filter_results": {
                    "hate": {"filtered": False, "severity": "safe"},
                    "self_harm": {"filtered": False, "severity": "safe"},
                    "sexual": {"filtered": False, "severity": "safe"},
                    "violence": {"filtered": False, "severity": "safe"},
                },
            },
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    }

    return Response(
        content=json.dumps(response_body),
        headers={
            "Content-Type": "application/json",
        },
        status_code=200,
    )


def _validate_api_key_header(context: RequestContext):
    request = context.request
    validate_api_key_header(request=request, header_name="api-key", allowed_key_value=context.config.simulator_api_key)


async def azure_openai_embedding(context: RequestContext) -> Response | None:
    request = context.request
    is_match, path_params = context.is_route_match(
        request=request, path="/openai/deployments/{deployment}/embeddings", methods=["POST"]
    )
    if not is_match:
        return None

    _validate_api_key_header(context)
    deployment_name = path_params["deployment"]
    request_body = await request.json()
    model = get_embedding_model_from_deployment_name(context, deployment_name)

    if model is None:
        return Response(
            status_code=404,
            content=json.dumps({"error": f"Deployment {deployment_name} not found"}),
            headers={
                "Content-Type": "application/json",
            },
        )
    request_input = request_body["input"]

    response = create_embeddings_response(
        context=context,
        deployment_name=deployment_name,
        deployment=model,
        request_input=request_input,
    )

    # calculate a simulated latency and store in context.values
    # needs to be called after the response has been created
    await calculate_latency(context, 200)

    return response


async def azure_openai_completion(context: RequestContext) -> Response | None:
    request = context.request
    is_match, path_params = context.is_route_match(
        request=request, path="/openai/deployments/{deployment}/completions", methods=["POST"]
    )
    if not is_match:
        return None

    _validate_api_key_header(context)

    deployment_name = path_params["deployment"]
    model_name = get_model_name_from_deployment_name(context, deployment_name)
    if model_name is None:
        return Response(
            status_code=404,
            content=json.dumps({"error": f"Deployment {deployment_name} not found"}),
            headers={
                "Content-Type": "application/json",
            },
        )
    request_body = await request.json()
    prompt_tokens = num_tokens_from_string(request_body["prompt"], model_name)

    requested_max_tokens, max_tokens = get_max_completion_tokens(request_body, model_name, prompt_tokens=prompt_tokens)

    context.values[SIMULATOR_KEY_OPENAI_MAX_TOKENS_REQUESTED] = requested_max_tokens
    context.values[SIMULATOR_KEY_OPENAI_MAX_TOKENS_EFFECTIVE] = max_tokens

    response = create_completion_response(
        context=context,
        deployment_name=deployment_name,
        model_name=model_name,
        prompt_tokens=prompt_tokens,
        max_tokens=max_tokens,
    )

    # calculate a simulated latency and store in context.values
    # needs to be called after the response has been created
    await calculate_latency(context, 200)

    return response


async def azure_openai_chat_completion(context: RequestContext) -> Response | None:
    request = context.request
    is_match, path_params = context.is_route_match(
        request=request, path="/openai/deployments/{deployment}/chat/completions", methods=["POST"]
    )
    if not is_match:
        return None

    _validate_api_key_header(context)

    request_body = await request.json()
    deployment_name = path_params["deployment"]
    model_name = get_model_name_from_deployment_name(context, deployment_name)
    if model_name is None:
        return Response(
            status_code=404,
            content=json.dumps({"error": f"Deployment {deployment_name} not found"}),
            headers={
                "Content-Type": "application/json",
            },
        )
    messages = request_body["messages"]
    prompt_tokens = num_tokens_from_messages(messages, model_name)

    requested_max_tokens, max_tokens = get_max_completion_tokens(request_body, model_name, prompt_tokens=prompt_tokens)

    context.values[SIMULATOR_KEY_OPENAI_MAX_TOKENS_REQUESTED] = requested_max_tokens
    context.values[SIMULATOR_KEY_OPENAI_MAX_TOKENS_EFFECTIVE] = max_tokens

    streaming = request_body.get("stream", False)

    response = create_lorem_chat_completion_response(
        context=context,
        deployment_name=deployment_name,
        model_name=model_name,
        streaming=streaming,
        max_tokens=max_tokens,
        prompt_messages=messages,
    )

    # calculate a simulated latency and store in context.values
    # needs to be called after the response has been created
    await calculate_latency(context, 200)

    return response


async def azure_openai_translation(context: RequestContext) -> Response | None:
    request = context.request
    is_match, path_params = context.is_route_match(
        request=request, path="/openai/deployments/{deployment}/audio/translations", methods=["POST"]
    )
    if not is_match:
        return None

    _validate_api_key_header(context)

    deployment_name = path_params["deployment"]
    model_name = get_model_name_from_deployment_name(context, deployment_name)
    if model_name is None:
        return Response(
            status_code=404,
            content=json.dumps({"error": f"Deployment {deployment_name} not found"}),
            headers={
                "Content-Type": "application/json",
            },
        )
    request_form = await request.form()
    audio_file = request_form["file"]
    response_format = request_form["response_format"]

    file_size = len(audio_file.file.read())

    max_tokens = 200

    # context.values[SIMULATOR_KEY_OPENAI_MAX_TOKENS_REQUESTED] = requested_max_tokens
    context.values[SIMULATOR_KEY_OPENAI_MAX_TOKENS_EFFECTIVE] = max_tokens

    response = create_translation_response(
        context=context,
        response_format=response_format,
        deployment_name=deployment_name,
        model_name=model_name,
        max_tokens=max_tokens,
    )

    # calculate a simulated latency and store in context.values
    # needs to be called after the response has been created
    await calculate_latency(context, 200)

    return response
