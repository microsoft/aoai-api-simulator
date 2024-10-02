"""
Test the OpenAI generator endpoints
"""

import logging

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
from openai import AuthenticationError, AzureOpenAI, BadRequestError, NotFoundError, RateLimitError

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
        "deployment2": OpenAIDeployment(
            name="deployment2",
            model=model_catalogue["text-embedding-ada-001"],
            embedding_size=768,
            tokens_per_minute=10000,
        ),
        "deployment3": OpenAIDeployment(
            name="deployment3",
            model=model_catalogue["text-embedding-3-small"],
            embedding_size=1536,
            tokens_per_minute=10000,
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
            azure_endpoint=ENDPOINT,
            max_retries=0,
        )
        content = "This is some text to generate embeddings for"

        with pytest.raises(AuthenticationError) as e:
            aoai_client.embeddings.create(model="deployment1", input=content)

        assert e.value.status_code == 401
        assert e.value.message == "Error code: 401 - {'detail': 'Missing or incorrect API Key'}"


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
            azure_endpoint=ENDPOINT,
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
            azure_endpoint=ENDPOINT,
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
        with pytest.raises(RateLimitError) as e:
            aoai_client.chat.completions.create(model="low_limit", messages=messages, max_tokens=50)

        assert e.value.status_code == 429
        assert (
            e.value.message
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
            azure_endpoint=ENDPOINT,
            max_retries=0,
        )
        content = "This is some text to generate embeddings for"

        with pytest.raises(NotFoundError) as e:
            aoai_client.embeddings.create(model="_unknown_deployment_", input=content)

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
        content = "This is some text to generate embeddings for"
        response = aoai_client.embeddings.create(model="_unknown_deployment_", input=content)

        assert len(response.data) == 1


@pytest.mark.asyncio
async def test_pass_in_dimension_param_for_supported_model():
    """
    Test that the dimension parameter is passed in to embeddings generation
    and overrides the embedding size set in a deployment
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
        content = "This is some text to generate embeddings for"
        response = aoai_client.embeddings.create(model="deployment3", input=content, dimensions=10)

        assert len(response.data[0].embedding) == 10


@pytest.mark.asyncio
async def test_pass_in_dimension_param_for_unsupported_model_ignored():
    """
    Test that passing in dimension parameter to embeddings generation
    fails when the model does not support overriding embedding size
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
        content = "This is some text to generate embeddings for"
        # deployment1 will ignore the dimensions parameter
        response = aoai_client.embeddings.create(model="deployment1", input=content, dimensions=10)

        logger = logging.getLogger(__name__)
        logger.error(response)

        # Dimension parameter is ignored and the default embeddingSize is used
        assert len(response.data[0].embedding) == 1536


@pytest.mark.asyncio
async def test_using_unsupported_model_for_embeddings_returns_400():
    """
    Test that passing in an unsupported model name to embeddings generation
    fails with 400 Bad Request
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
        content = "This is some text to generate embeddings for"
        with pytest.raises(BadRequestError) as e:
            aoai_client.embeddings.create(model="low_limit", input=content, dimensions=10)

        assert e.value.status_code == 400
        assert (
            e.value.message
            == "Error code: 400 - {'error': {'code': 'OperationNotSupported', 'message': 'The embeddings operation does not work with the specified model, low_limit. Please choose different model and try again. You can learn more about which models can be used with each operation here: https://go.microsoft.com/fwlink/?linkid=2197993.'}}"
        )
