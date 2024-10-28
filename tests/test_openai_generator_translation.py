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
from openai import AzureOpenAI, RateLimitError

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
        "whisper": OpenAIDeployment(name="whisper", model=model_catalogue["whisper"], requests_per_minute=64 * 6),
        "low_limit": OpenAIDeployment(name="low_limit", model=model_catalogue["whisper"], requests_per_minute=1),
    }
    config.extension_path = extension_path
    return config


@pytest.mark.asyncio
async def test_success():
    """
    Ensure we can call the translation endpoint
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

        with open("/workspaces/aoai-api-simulator/tests/audio/short-white-noise.mp3", "rb") as file:
            response = aoai_client.audio.translations.create(model="whisper", file=file, response_format="json")

        assert len(response.text) > 0


@pytest.mark.asyncio
async def test_when_response_format_is_text_returns_text():
    """
    Ensure we can call the translation endpoint
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

        with open("/workspaces/aoai-api-simulator/tests/audio/short-white-noise.mp3", "rb") as file:
            response = aoai_client.audio.translations.create(model="whisper", file=file, response_format="text")

        assert '"text":' not in response
        assert len(response) > 0


@pytest.mark.asyncio
async def test_returns_413_when_file_too_large():
    """
    Ensure we get a 413
    """
    file_to_test = "/workspaces/aoai-api-simulator/tests/audio/over-large-audio-file-white-noise.mp3"
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint=ENDPOINT,
            max_retries=0,
        )

        with open(file_to_test, "rb") as file:
            with pytest.raises(Exception) as e:
                aoai_client.audio.translations.create(model="whisper", file=file, response_format="json")
                assert e.value.status_code == 413


@pytest.mark.asyncio
async def test_limit_reached():
    """
    Ensure we can call the translations endpoint multiple times using the generator to trigger rate-limiting
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
        with open("/workspaces/aoai-api-simulator/tests/audio/short-white-noise.mp3", "rb") as file:
            response = aoai_client.audio.translations.create(model="low_limit", file=file, response_format="json")

        assert len(response.text) > 0

        # "low_limit" deployment has a rate limit of 1 request per minute
        with pytest.raises(RateLimitError) as e:
            with open("/workspaces/aoai-api-simulator/tests/audio/short-white-noise.mp3", "rb") as file:
                aoai_client.audio.translations.create(model="low_limit", file=file, response_format="text")

        assert e.value.status_code == 429
        assert (
            e.value.message
            == "Error code: 429 - {'error': {'code': '429', 'message': 'Requests to the OpenAI API Simulator have exceeded call rate limit. Please retry after 60 seconds.'}}"
        )
