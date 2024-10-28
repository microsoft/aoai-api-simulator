import json
import logging

import requests
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
    SIMULATOR_KEY_OPENAI_PROMPT_TOKENS,
    SIMULATOR_KEY_OPENAI_TOTAL_TOKENS,
    SIMULATOR_KEY_OPERATION_NAME,
)
from aoai_api_simulator.models import RequestContext

# This file contains a default openai forwarder
# You can configure your own forwarders by creating a forwarder_config.py file and setting the
# EXTENSION_PATH environment variable to the path of the file when running the API
# See examples/forwarder_doc_intelligence for an example of how to define your own forwarders

config_validated: bool = False

logger = logging.getLogger(__name__)


def _validate_endpoint_config(context: RequestContext):
    # pylint: disable-next=global-statement
    global config_validated

    aoai_api_endpoint = context.config.recording.aoai_api_endpoint
    aoai_api_key = context.config.recording.aoai_api_key

    config_validated = True  # only show the message once

    if aoai_api_key and aoai_api_endpoint:
        logger.info("🚀 Initialized Azure OpenAI forwarder with the following settings:")
        logger.info("🔑 API endpoint: %s", aoai_api_endpoint)
        masked_api_key = aoai_api_key[:4] + "..." + aoai_api_key[-4:]
        logger.info("🔑 API key: %s", masked_api_key)

    else:
        logger.warning(
            "Got a request that looked like an openai request, but missing some or all of the "
            + "required environment variables for forwarding: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY"
        )


aoai_response_headers_to_remove = [
    # Strip out header values we aren't interested in - this also helps to reduce the recording file size
    "apim-request-id",
    "azureml-model-session",
    "x-accel-buffering",
    "x-content-type-options",
    "x-ms-client-request-id",
    "x-ms-region",
    "x-request-id",
    "Cache-Control",
    "Content-Length",
    "Date",
    "Strict-Transport-Security",
    "access-control-allow-origin",
    # "x-ratelimit-remaining-requests",
    # "x-ratelimit-remaining-tokens",
]


def _get_deployment_name_from_url(url: str) -> str | None:
    # Extract deployment name from /openai/deployments/{deployment_name}/operation
    if url.startswith("/openai/deployments/"):
        url = url[len("/openai/deployments/") :]
        deployment_name = url.split("/")[0]
        return deployment_name
    return None


def _get_token_usage_from_response(body: str) -> int | None:
    try:
        response_json = json.loads(body)

        usage = response_json.get("usage")
        if usage is not None:
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            return prompt_tokens, completion_tokens, total_tokens
    except json.JSONDecodeError as e:
        logger.error("Error getting token usage: %s", e)
    return None


def _get_operation_name_from_url(url: str) -> str | None:
    # Extract operation name from /openai/deployments/{deployment_name}/{operation}
    url = url.lower()
    if url.startswith("/openai/deployments/"):
        url = url[len("/openai/deployments/") :]
        i = url.find("/")
        if i < 0:
            return None
        url = url[i + 1 :]

        if url.startswith("completions"):
            return OPENAI_OPERATION_COMPLETIONS
        if url.startswith("chat/completions"):
            return OPENAI_OPERATION_CHAT_COMPLETIONS
        if url.startswith("embeddings"):
            return OPENAI_OPERATION_EMBEDDINGS
        if url.startswith("translations"):
            return OPENAI_OPERATION_TRANSLATION
    return None


def _is_token_operation(operation_name: str):
    return operation_name in [
        OPENAI_OPERATION_EMBEDDINGS,
        OPENAI_OPERATION_COMPLETIONS,
        OPENAI_OPERATION_CHAT_COMPLETIONS,
    ]


async def forward_to_azure_openai(context: RequestContext) -> dict:
    if not context.is_openai_request():
        # assume not an OpenAI request
        return None

    request = context.request

    if not config_validated:
        # Only initialize once, and only if we need to
        _validate_endpoint_config(context)

    aoai_api_endpoint = context.config.recording.aoai_api_endpoint
    aoai_api_key = context.config.recording.aoai_api_key

    if aoai_api_key is None or aoai_api_endpoint is None:
        return None

    url = aoai_api_endpoint
    if url.endswith("/"):
        url = url[:-1]
    url += request.url.path + "?" + request.url.query

    # Copy most headers, but override auth
    fwd_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in ["content-length", "host", "authorization"]
    }
    fwd_headers["api-key"] = aoai_api_key

    body = await request.body()

    response = requests.request(
        request.method,
        url,
        headers=fwd_headers,
        data=body,
        timeout=30,
    )

    for header in aoai_response_headers_to_remove:
        if response.headers.get(header):
            del response.headers[header]

    if response.status_code >= 300:
        # Likely an error or rate-limit
        # no further processing - indicate not to persist this response
        return {"response": response, "persist_response": False}

    # store values in the context for use by the rate-limiter etc
    deployment_name = _get_deployment_name_from_url(request.url.path)
    context.values[SIMULATOR_KEY_DEPLOYMENT_NAME] = deployment_name

    operation_name = _get_operation_name_from_url(request.url.path)
    context.values[SIMULATOR_KEY_OPERATION_NAME] = operation_name
    if _is_token_operation(operation_name):
        context.values[SIMULATOR_KEY_LIMITER] = LIMITER_OPENAI_TOKENS
        prompt_tokens, completion_tokens, total_tokens = _get_token_usage_from_response(response.text)
        context.values[SIMULATOR_KEY_OPENAI_PROMPT_TOKENS] = prompt_tokens
        context.values[SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS] = completion_tokens
        context.values[SIMULATOR_KEY_OPENAI_TOTAL_TOKENS] = total_tokens
    else:
        context.values[SIMULATOR_KEY_LIMITER] = LIMITER_OPENAI_REQUESTS

    return {"response": response, "persist_response": True}
