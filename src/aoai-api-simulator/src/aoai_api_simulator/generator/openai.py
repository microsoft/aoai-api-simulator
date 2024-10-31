import asyncio
import json
import logging
import random
import time

import nanoid
from aoai_api_simulator import constants
from aoai_api_simulator.auth import validate_api_key_header
from aoai_api_simulator.constants import (
    LIMITER_OPENAI_REQUESTS,
    LIMITER_OPENAI_TOKENS,
    OPENAI_OPERATION_CHAT_COMPLETIONS,
    OPENAI_OPERATION_COMPLETIONS,
    OPENAI_OPERATION_EMBEDDINGS,
    OPENAI_OPERATION_TRANSLATION,
    SIMULATOR_KEY_DEPLOYMENT_NAME,
    SIMULATOR_KEY_LIMITER,
    SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS,
    SIMULATOR_KEY_OPENAI_MAX_TOKENS_EFFECTIVE,
    SIMULATOR_KEY_OPENAI_MAX_TOKENS_REQUESTED,
    SIMULATOR_KEY_OPENAI_PROMPT_TOKENS,
    SIMULATOR_KEY_OPENAI_REQUEST_FILE_SIZE_BYTES,
    SIMULATOR_KEY_OPENAI_TOTAL_TOKENS,
    SIMULATOR_KEY_OPERATION_NAME,
)
from aoai_api_simulator.generator.lorem import generate_lorem_text
from aoai_api_simulator.generator.model_catalogue import model_catalogue
from aoai_api_simulator.generator.openai_tokens import (
    get_max_completion_tokens,
    num_tokens_from_messages,
    num_tokens_from_string,
)
from aoai_api_simulator.models import (
    OpenAIChatModel,
    OpenAIDeployment,
    OpenAIEmbeddingModel,
    OpenAIWhisperModel,
    RequestContext,
)
from fastapi import Response
from fastapi.responses import StreamingResponse

# This file contains a default implementation of the openai generators
# You can configure your own generators by creating a generator_config.py file and setting the
# EXTENSION_PATH environment variable to the path of the file when running the API
# See examples/generator_echo for an example of how to define your own generators

logger = logging.getLogger(__name__)

# API docs: https://learn.microsoft.com/en-gb/azure/ai-services/openai/reference

deployment_missing_warning_printed = set()
embedding_deployment_missing_warning_printed = set()
default_openai_embedding_model = OpenAIDeployment(
    name="embedding", model=model_catalogue["text-embedding-ada-002"], tokens_per_minute=10000, embedding_size=1536
)


def get_embedding_deployment_from_name(context: RequestContext, deployment_name: str) -> OpenAIDeployment | None:
    """
    Gets the embedding model for the specified embedding deployment.
    If the deployment is not in the configured deployments,
    then the default model is returned and a warning is logged.

    Args:
        context: RequestContext instance
        deployment_name: Name of the deployment

    Returns:
        OpenAIEmbeddingModel | None: Instance of OpenAIEmbeddingModel
    """
    deployments = context.config.openai_deployments

    if deployments:
        deployment = deployments.get(deployment_name)

        if deployment:
            return deployment

    if context.config.allow_undefined_openai_deployments:
        default_model_name = "embedding"

        # Output warning for missing embedding deployment name
        if deployment_name not in embedding_deployment_missing_warning_printed:
            # We only output the warning the first time we encounter the model is missing
            logger.warning(
                "Deployment %s not found in config and "
                "allow_undefined_openai_deployments is True. "
                "Using default model %s",
                deployment_name,
                default_model_name,
            )
            embedding_deployment_missing_warning_printed.add(default_model_name)
        return default_openai_embedding_model

    # Output warning for missing embedding deployment name
    # (only the first time we encounter it)
    if deployment_name not in deployment_missing_warning_printed:
        logger.warning(
            "Deployment %s not found in config and allow_undefined_openai_deployments is False", deployment_name
        )
        deployment_missing_warning_printed.add(deployment_name)
    return None


def get_chat_model_from_deployment_name(context: RequestContext, deployment_name: str) -> OpenAIChatModel | None:
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
        if deployment_name not in deployment_missing_warning_printed:
            logger.warning(
                "Deployment %s not found in config and allow_undefined_openai_deployments is True."
                + " Using default model %s",
                deployment_name,
                default_model,
            )
            deployment_missing_warning_printed.add(deployment_name)
        return model_catalogue[default_model]

    # Output warning for missing deployment name (only the first time we encounter it)
    if deployment_name not in deployment_missing_warning_printed:
        logger.warning(
            "Deployment %s not found in config and allow_undefined_openai_deployments is False", deployment_name
        )
        deployment_missing_warning_printed.add(deployment_name)
    return None


def get_whisper_model_from_deployment_name(context: RequestContext, deployment_name: str) -> OpenAIWhisperModel | None:
    """
    Gets the model name for the specified deployment.
    If the deployment is not in the configured deployments then either a default model is returned (if )
    """
    deployments = context.config.openai_deployments
    if deployments:
        deployment = deployments.get(deployment_name)
        if deployment:
            return deployment

    if context.config.allow_undefined_openai_deployments:
        default_model = "whisper"

        # Output warning for missing deployment name (only the first time we encounter it)
        if deployment_name not in deployment_missing_warning_printed:
            logger.warning(
                "Deployment %s not found in config and allow_undefined_openai_deployments is True."
                + " Using default model %s",
                deployment_name,
                default_model,
            )
            deployment_missing_warning_printed.add(deployment_name)
        return model_catalogue[default_model]

    # Output warning for missing deployment name (only the first time we encounter it)
    if deployment_name not in deployment_missing_warning_printed:
        logger.warning(
            "Deployment %s not found in config and allow_undefined_openai_deployments is False", deployment_name
        )
        deployment_missing_warning_printed.add(deployment_name)
    return None


async def calculate_latency_text_endpoints(context: RequestContext, status_code: int):
    """Calculate additional latency that should be applied"""
    if status_code >= 300:
        return

    operation_name = context.values.get(constants.SIMULATOR_KEY_OPERATION_NAME)
    config = context.config

    # Determine the target latency for the request
    completion_tokens = context.values.get(constants.SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS)
    if completion_tokens and completion_tokens > 0:
        target_duration_ms = None
        if operation_name == OPENAI_OPERATION_EMBEDDINGS:
            # embeddings config returns latency value to use (in milliseconds)
            target_duration_ms = config.latency.open_ai_embeddings.get_value()
        elif operation_name == OPENAI_OPERATION_COMPLETIONS:
            # completions config returns latency per completion token in milliseconds
            target_duration_ms = config.latency.open_ai_completions.get_value()
        elif operation_name == OPENAI_OPERATION_CHAT_COMPLETIONS:
            # chat completions config returns latency per completion token in milliseconds
            target_duration_ms = config.latency.open_ai_chat_completions.get_value() * completion_tokens

        if target_duration_ms:
            # store the target duration in the context for use by the apply_latency method
            context.values[constants.TARGET_DURATION_MS] = target_duration_ms


async def calculate_latency_translation(context: RequestContext, status_code: int):
    """Calculate additional latency that should be applied"""
    if status_code >= 300:
        return

    config = context.config
    # Determine the target latency for the request
    target_duration_ms = None

    # translation config returns latency per MB of input audio in milliseconds
    file_size_bytes = context.values.get(constants.SIMULATOR_KEY_OPENAI_REQUEST_FILE_SIZE_BYTES)
    if file_size_bytes is None:
        raise ValueError("Request file size not found in context values - unable to calculate latency")
    file_size_mb = file_size_bytes / 1024 / 1024
    target_duration_ms = config.latency.open_ai_translations.get_value() * file_size_mb

    if target_duration_ms:
        # store the target duration in the context for use by the apply_latency method
        context.values[constants.TARGET_DURATION_MS] = target_duration_ms


def create_embedding_content(index: int, embedding_size: int):
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
    dimension: int | None,
):
    embedding_size = deployment.embedding_size

    if dimension is not None:
        assert isinstance(deployment.model, OpenAIEmbeddingModel)
        if deployment.model.supports_custom_dimensions:
            embedding_size = dimension

    embeddings = []
    if isinstance(request_input, str):
        tokens = num_tokens_from_string(request_input, deployment.model.name)
        embeddings.append(create_embedding_content(0, embedding_size=embedding_size))
    else:
        tokens = 0
        index = 0
        for i in request_input:
            tokens += num_tokens_from_string(i, deployment.model.name)
            embeddings.append(create_embedding_content(index, embedding_size=embedding_size))
            index += 1

    response_data = {
        "object": "list",
        "data": embeddings,
        "model": deployment.model.name,
        "usage": {"prompt_tokens": tokens, "total_tokens": tokens},
    }

    # store values in the context for use by the rate-limiter etc
    context.values[SIMULATOR_KEY_LIMITER] = LIMITER_OPENAI_TOKENS
    context.values[SIMULATOR_KEY_OPERATION_NAME] = OPENAI_OPERATION_EMBEDDINGS
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
    context.values[SIMULATOR_KEY_LIMITER] = LIMITER_OPENAI_TOKENS
    context.values[SIMULATOR_KEY_OPERATION_NAME] = OPENAI_OPERATION_COMPLETIONS
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


# pylint: disable-next=too-many-arguments, too-many-positional-arguments
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


# pylint: disable-next=too-many-arguments, too-many-positional-arguments
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
    context.values[SIMULATOR_KEY_LIMITER] = LIMITER_OPENAI_TOKENS
    context.values[SIMULATOR_KEY_OPERATION_NAME] = OPENAI_OPERATION_CHAT_COMPLETIONS
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
    deployment = get_embedding_deployment_from_name(context, deployment_name)

    if deployment is None:
        return Response(
            status_code=404,
            content=json.dumps({"error": f"Deployment {deployment_name} not found"}),
            headers={
                "Content-Type": "application/json",
            },
        )

    if not isinstance(deployment.model, OpenAIEmbeddingModel):
        return Response(
            status_code=400,
            content=json.dumps(
                {
                    "error": {
                        "code": "OperationNotSupported",
                        "message": "The embeddings operation does not work with the specified model, "
                        + deployment_name
                        + ". Please choose different model and try again. "
                        + "You can learn more about which models can be used with each operation here: "
                        + "https://go.microsoft.com/fwlink/?linkid=2197993.",
                    }
                }
            ),
            headers={
                "Content-Type": "application/json",
            },
        )
    request_input = request_body["input"]

    response = create_embeddings_response(
        context=context,
        deployment_name=deployment_name,
        deployment=deployment,
        request_input=request_input,
        dimension=request_body["dimensions"] if "dimensions" in request_body else None,
    )

    # calculate a simulated latency and store in context.values
    # needs to be called after the response has been created
    await calculate_latency_text_endpoints(context, 200)

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
    model = get_chat_model_from_deployment_name(context, deployment_name)
    if model is None:
        return Response(
            status_code=404,
            content=json.dumps({"error": f"Deployment {deployment_name} not found"}),
            headers={
                "Content-Type": "application/json",
            },
        )

    if not isinstance(model, OpenAIChatModel):
        return Response(
            status_code=400,
            content=json.dumps(
                {
                    "error": {
                        "code": "OperationNotSupported",
                        "message": "The completions operation does not work with the specified model, "
                        + deployment_name
                        + ". Please choose different model and try again. "
                        + "You can learn more about which models can be used with each operation here: "
                        + "https://go.microsoft.com/fwlink/?linkid=2197993.",
                    }
                }
            ),
            headers={
                "Content-Type": "application/json",
            },
        )
    request_body = await request.json()
    prompt_tokens = num_tokens_from_string(request_body["prompt"], model.name)

    requested_max_tokens, max_tokens = get_max_completion_tokens(request_body, model.name, prompt_tokens=prompt_tokens)

    context.values[SIMULATOR_KEY_OPENAI_MAX_TOKENS_REQUESTED] = requested_max_tokens
    context.values[SIMULATOR_KEY_OPENAI_MAX_TOKENS_EFFECTIVE] = max_tokens

    response = create_completion_response(
        context=context,
        deployment_name=deployment_name,
        model_name=model.name,
        prompt_tokens=prompt_tokens,
        max_tokens=max_tokens,
    )

    # calculate a simulated latency and store in context.values
    # needs to be called after the response has been created
    await calculate_latency_text_endpoints(context, 200)

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
    model = get_chat_model_from_deployment_name(context, deployment_name)
    if model is None:
        return Response(
            status_code=404,
            content=json.dumps({"error": f"Deployment {deployment_name} not found"}),
            headers={
                "Content-Type": "application/json",
            },
        )
    if not isinstance(model, OpenAIChatModel):
        return Response(
            status_code=400,
            content=json.dumps(
                {
                    "error": {
                        "code": "OperationNotSupported",
                        "message": "The chatCompletion operation does not work with the specified model, "
                        + deployment_name
                        + ". Please choose different model and try again. "
                        + "You can learn more about which models can be used with each operation here: "
                        + "https://go.microsoft.com/fwlink/?linkid=2197993.",
                    }
                }
            ),
            headers={
                "Content-Type": "application/json",
            },
        )

    messages = request_body["messages"]
    prompt_tokens = num_tokens_from_messages(messages, model.name)

    requested_max_tokens, max_tokens = get_max_completion_tokens(request_body, model.name, prompt_tokens=prompt_tokens)

    context.values[SIMULATOR_KEY_OPENAI_MAX_TOKENS_REQUESTED] = requested_max_tokens
    context.values[SIMULATOR_KEY_OPENAI_MAX_TOKENS_EFFECTIVE] = max_tokens

    streaming = request_body.get("stream", False)

    response = create_lorem_chat_completion_response(
        context=context,
        deployment_name=deployment_name,
        model_name=model.name,
        streaming=streaming,
        max_tokens=max_tokens,
        prompt_messages=messages,
    )

    # calculate a simulated latency and store in context.values
    # needs to be called after the response has been created
    await calculate_latency_text_endpoints(context, 200)

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
    model = get_whisper_model_from_deployment_name(context, deployment_name)
    if model is None:
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
    context.values[SIMULATOR_KEY_OPENAI_REQUEST_FILE_SIZE_BYTES] = file_size

    if file_size == 0 or file_size > 26214400:
        return Response(
            status_code=413,
            content=json.dumps(
                {
                    "error": {
                        "message": f"Maximum content size limit (26214400) exceeded ({file_size} bytes read)",
                        "type": "server_error",
                        "param": "null",
                        "code": "null",
                    }
                }
            ),
            headers={
                "Content-Type": "application/json",
            },
        )

    max_tokens_to_generate = 10 if file_size < 1000 else (file_size // 1000) * 10

    response = create_translation_response(
        context=context,
        response_format=response_format,
        deployment_name=deployment_name,
        max_tokens_to_generate=max_tokens_to_generate,
    )

    # calculate a simulated latency and store in context.values
    # needs to be called after the response has been created
    await calculate_latency_translation(context, 200)

    return response


def create_translation_response(
    context: RequestContext, response_format: str, deployment_name: str, max_tokens_to_generate: int
):
    """
    Creates a Response object for a translation request and sets context values for the rate-limiter etc
    """

    # Generate response text based max_tokens_to_generate
    text = generate_lorem_text(max_tokens=max_tokens_to_generate, model_name="gpt-3.5-turbo-0301")

    content = text
    if response_format == "json":
        json_result = {"text": text}
        content = json.dumps(json_result)
    # TODO: Handle other response formats
    # see https://learn.microsoft.com/en-us/azure/ai-services/openai/reference#audioresponseformat

    context.values[SIMULATOR_KEY_LIMITER] = LIMITER_OPENAI_REQUESTS
    context.values[SIMULATOR_KEY_OPERATION_NAME] = OPENAI_OPERATION_TRANSLATION
    context.values[SIMULATOR_KEY_DEPLOYMENT_NAME] = deployment_name

    return Response(
        content=content,
        headers={
            "Content-Type": "application/json" if response_format == "json" else "text/plain",
        },
        status_code=200,
    )
