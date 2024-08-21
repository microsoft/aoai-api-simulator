"""
Test the OpenAI generator endpoints
"""

from aoai_api_simulator.models import (
    Config,
    LatencyConfig,
    ChatCompletionLatency,
    CompletionLatency,
    EmbeddingLatency,
    OpenAIDeployment,
)
from aoai_api_simulator.generator.manager import get_default_generators
from openai import AzureOpenAI, AuthenticationError, NotFoundError, RateLimitError, Stream
from openai.types.chat import ChatCompletionChunk
import pytest

from .test_uvicorn_server import UvicornTestServer

API_KEY = "123456789"


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
        "low_limit": OpenAIDeployment(name="low_limit", model="gpt-3.5-turbo", tokens_per_minute=64 * 6),
        "deployment1": OpenAIDeployment(
            name="text-embedding-ada-002", model="text-embedding-ada-002", embedding_size=1536, tokens_per_minute=10000
        ),
        "deployment2": OpenAIDeployment(
            name="text-embedding-ada-001", model="text-embedding-ada-001", embedding_size=768, tokens_per_minute=10000
        ),
    }
    config.extension_path = extension_path
    return config


@pytest.mark.asyncio
async def test_requires_auth():
    """
    Ensure we need the right API key to call the embeddings endpoint
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key="wrong_key",
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )
        content = "This is some text to generate embeddings for"

        try:
            aoai_client.embeddings.create(model="deployment1", input=content)
            assert False, "Expected an exception"
        except AuthenticationError as e:
            assert e.status_code == 401
            assert e.message == "Error code: 401 - {'detail': 'Missing or incorrect API Key'}"


@pytest.mark.asyncio
async def test_success():
    """
    Ensure we can call the embeddings endpoint using the generator
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )

        # Check with deployment1
        content = "This is some text to generate embeddings for"
        response = aoai_client.embeddings.create(model="deployment1", input=content)
        assert len(response.data) == 1
        assert response.data[0].object == "embedding"
        assert response.data[0].index == 0
        assert len(response.data[0].embedding) == 1536

        # Check with deployment 2
        content = "This is some text to generate embeddings for"
        response = aoai_client.embeddings.create(model="deployment2", input=content)
        assert len(response.data) == 1
        assert response.data[0].object == "embedding"
        assert response.data[0].index == 0
        assert len(response.data[0].embedding) == 768


@pytest.mark.asyncio
async def test_limit_reached():
    """
    Ensure we can call the chat completions endpoint multiple times using the generator to trigger rate-limiting
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )
        messages = [{"role": "user", "content": "What is the meaning of life?"}]
        response = aoai_client.chat.completions.create(model="low_limit", messages=messages, max_tokens=50)

        assert len(response.choices) == 1
        assert response.choices[0].message.role == "assistant"
        assert len(response.choices[0].message.content) > 20
        assert response.choices[0].finish_reason == "length"

        # "low_limit" deployment has a rate limit of 600 tokens per minute
        # So we will trigger the limit based on the number of requests (not tokens)
        # and it will reset in 10s
        try:
            aoai_client.chat.completions.create(model="low_limit", messages=messages, max_tokens=50)
            assert False, "Expect to be rate-limited"
        except RateLimitError as e:
            assert e.status_code == 429
            assert (
                e.message
                == "Error code: 429 - {'error': {'code': '429', 'message': 'Requests to the OpenAI API Simulator have exceeded call rate limit. Please retry after 10 seconds.'}}"
            )


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
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )
        content = "This is some text to generate embeddings for"
        try:
            aoai_client.embeddings.create(model="_unknown_deployment_", input=content)
            assert False, "Expected 404 error"
        except NotFoundError as e:
            assert e.status_code == 404
            assert e.message == "Error code: 404 - {'error': 'Deployment _unknown_deployment_ not found'}"


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
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )
        content = "This is some text to generate embeddings for"
        response = aoai_client.embeddings.create(model="_unknown_deployment_", input=content)

        assert len(response.data) == 1
