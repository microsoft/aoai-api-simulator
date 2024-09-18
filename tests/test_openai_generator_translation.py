"""
Test the OpenAI generator endpoints
"""

import json

import pytest
from aoai_api_simulator.generator.manager import get_default_generators
from aoai_api_simulator.models import (
    ChatCompletionLatency,
    CompletionLatency,
    Config,
    EmbeddingLatency,
    LatencyConfig,
    OpenAIDeployment,
)
from openai import AzureOpenAI

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
        "whisper": OpenAIDeployment(name="whisper", model="whisper-1", tokens_per_minute=64 * 6)
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
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )

        file = open("/workspaces/aoai-api-simulator/tests/audio/In-demo-1min-Vietnamese-UN-Speech.mp3", "rb")
        response = aoai_client.audio.translations.create(model="whisper", file=file, response_format="json")

        file.close()
        result = json.loads(response.data)
        assert len(result["text"]) > 0


@pytest.mark.asyncio
async def test_returns_413_when_file_too_large():
    """
    Ensure we get a 413
    """
    file_to_test = "/workspaces/aoai-api-simulator/tests/audio/over-large-audio-file.mp3"
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        aoai_client = AzureOpenAI(
            api_key=API_KEY,
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8001",
            max_retries=0,
        )

        file = open(file_to_test, "rb")

        with pytest.raises(Exception) as e:
            aoai_client.audio.translations.create(model="whisper", file=file, response_format="json")
            assert e.value.status_code == 413
        file.close()
