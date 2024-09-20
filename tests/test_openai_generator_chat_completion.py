"""
Test the OpenAI generator endpoints
"""

import pytest
from aoai_api_simulator.generator.manager import get_default_generators
from aoai_api_simulator.generator.model_catalogue import model_catalogue
from aoai_api_simulator.models import (
    ChatCompletionLatency,
    CompletionLatency,
    Config,
    EmbeddingLatency,
    LatencyConfig,
    OpenAIDeployment,
)
from openai import AuthenticationError, AzureOpenAI, BadRequestError, NotFoundError, Stream
from openai.types.chat import ChatCompletionChunk

from .test_uvicorn_server import UvicornTestServer

API_KEY = "123456789"
ENDPOINT = "http://localhost:8001"


def _get_generator_config(extension_path: str | None = None) -> Config:
    config = Config(generators=get_default_generators())
    config.simulator_api_key = API_KEY
    config.simulator_mode = "generate"
    config.latency = LatencyConfig(
        open_ai_completions=CompletionLatency(
            LATENCY_OPENAI_COMPLETIONS_MEAN=0,
            LATENCY_OPENAI_COMPLETIONS_STD_DEV=0.1,
        ),
        open_ai_chat_completions=ChatCompletionLatency(
            LATENCY_OPENAI_CHAT_COMPLETIONS_MEAN=0,
            LATENCY_OPENAI_CHAT_COMPLETIONS_STD_DEV=0.1,
        ),
        open_ai_embeddings=EmbeddingLatency(
            LATENCY_OPENAI_EMBEDDINGS_MEAN=0,
            LATENCY_OPENAI_EMBEDDINGS_STD_DEV=0.1,
        ),
    )
    config.openai_deployments = {
        "low_limit": OpenAIDeployment(
            name="low_limit", model=model_catalogue["gpt-3.5-turbo"], tokens_per_minute=64 * 6
        ),
        "deployment1": OpenAIDeployment(
            name="deployment1",
            model=model_catalogue["text-embedding-ada-002"],
            embedding_size=1536,
            tokens_per_minute=10000,
        ),
        "gpt-3.5-10m": OpenAIDeployment(
            name="gpt-3.5-10m,",
            model=model_catalogue["gpt-3.5-turbo"],
            tokens_per_minute=10000000,
        ),
    }
    config.extension_path = extension_path
    return config


@pytest.mark.asyncio
async def test_requires_auth():
    """
    Ensure we need the right API key to call the chat completion endpoint
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key="wrong_key",
            api_version="2023-12-01-preview",
            azure_endpoint=ENDPOINT,
            max_retries=0,
        )
        messages = [{"role": "user", "content": "What is the meaning of life?"}]

        with pytest.raises(AuthenticationError) as e:
            aoai_client.chat.completions.create(model="deployment1", messages=messages, max_tokens=50)

        assert e.value.status_code == 401
        assert e.value.message == "Error code: 401 - {'detail': 'Missing or incorrect API Key'}"


@pytest.mark.asyncio
async def test_success():
    """
    Ensure we can call the chat completion endpoint using the generator
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint=ENDPOINT,
            max_retries=0,
        )
        messages = [{"role": "user", "content": "What is the meaning of life?"}]
        max_tokens = 50
        response = aoai_client.chat.completions.create(model="low_limit", messages=messages, max_tokens=max_tokens)

        assert len(response.choices) == 1
        assert response.choices[0].message.role == "assistant"
        assert len(response.choices[0].message.content) > 20
        assert response.choices[0].finish_reason == "length"
        assert response.usage.completion_tokens <= max_tokens


@pytest.mark.asyncio
async def test_requires_known_deployment_when_config_set():
    """
    Test that the generator requires a known deployment when the ALLOW_UNDEFINED_OPENAI_DEPLOYMENTS config is set to False
    """
    config = _get_generator_config()
    config.allow_undefined_openai_deployments = False
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint=ENDPOINT,
            max_retries=0,
        )
        messages = [{"role": "user", "content": "What is the meaning of life?"}]
        max_tokens = 50

        with pytest.raises(NotFoundError) as e:
            aoai_client.chat.completions.create(model="_unknown_deployment_", messages=messages, max_tokens=max_tokens)

        assert e.value.status_code == 404
        assert e.value.message == "Error code: 404 - {'error': 'Deployment _unknown_deployment_ not found'}"


@pytest.mark.asyncio
async def test_allows_unknown_deployment_when_config_not_set():
    """
    Test that the generator allows an unknown deployment when the ALLOW_UNDEFINED_OPENAI_DEPLOYMENTS config is set to True
    """
    config = _get_generator_config()
    config.allow_undefined_openai_deployments = True
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint=ENDPOINT,
            max_retries=0,
        )
        messages = [{"role": "user", "content": "What is the meaning of life?"}]
        max_tokens = 50
        response = aoai_client.chat.completions.create(
            model="_unknown_deployment_", messages=messages, max_tokens=max_tokens
        )

        assert len(response.choices) == 1


@pytest.mark.asyncio
@pytest.mark.slow
async def test_max_tokens():
    """
    Ensure we can call the chat completion endpoint using the generator
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint=ENDPOINT,
            max_retries=0,
        )
        messages = [{"role": "user", "content": "What is the meaning of life?"}]
        max_tokens = 50

        # Make repeated requests to ensure that none exceed max_tokens
        for _ in range(1000):
            response = aoai_client.chat.completions.create(
                model="gpt-3.5-10m", messages=messages, max_tokens=max_tokens
            )
            assert response.usage.completion_tokens <= max_tokens


@pytest.mark.asyncio
async def test_stream_success():
    """
    Ensure we can call the chat completion endpoint using the generator with a streamed response
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint=ENDPOINT,
            max_retries=0,
        )
        messages = [{"role": "user", "content": "What is the meaning of life?"}]
        response: Stream[ChatCompletionChunk] = aoai_client.chat.completions.create(
            model="low_limit", messages=messages, max_tokens=50, stream=True
        )

        is_first_chunk = True
        count = 0
        chunk: ChatCompletionChunk
        for chunk in response:
            if is_first_chunk:
                is_first_chunk = False
                assert chunk.choices[0].delta.role == "assistant"
            assert len(chunk.choices) == 1
            count += 1

        assert count > 5
        assert chunk.choices[0].delta.finish_reason == "length"


@pytest.mark.asyncio
async def test_custom_generator():
    """
    Ensure we can call the chat completion endpoint using a generator from an extension
    """
    config = _get_generator_config(extension_path="examples/generator_replace_chat_completion/generator_config.py")

    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint=ENDPOINT,
            max_retries=0,
        )
        messages = [{"role": "user", "content": "What is the meaning of life?"}]
        response = aoai_client.chat.completions.create(model="low_limit", messages=messages, max_tokens=50)

        assert len(response.choices) == 1
        assert response.choices[0].message.role == "assistant"
        assert response.usage.completion_tokens <= 10, "Custom generator hard-codes max_tokens to 10"
        assert response.choices[0].finish_reason == "stop"


@pytest.mark.asyncio
async def test_using_unsupported_model_for_completions_returns_400():
    """
    Test that passing in an unsupported model name to chat completion generation
    fails with 400 Bad Request
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint=ENDPOINT,
            max_retries=0,
        )
        with pytest.raises(BadRequestError) as e:
            messages = [{"role": "user", "content": "What is the meaning of life?"}]
            aoai_client.chat.completions.create(model="deployment1", messages=messages, max_tokens=50)

        assert e.value.status_code == 400
        assert (
            e.value.message
            == "Error code: 400 - {'error': {'code': 'OperationNotSupported', 'message': 'The chatCompletion operation does not work with the specified model, deployment1. Please choose different model and try again. You can learn more about which models can be used with each operation here: https://go.microsoft.com/fwlink/?linkid=2197993.'}}"
        )
