"""
Test extension loading
"""

from aoai_api_simulator.config_loader import initialize_config
from aoai_api_simulator.generator.manager import get_default_generators
from aoai_api_simulator.models import (
    Config,
    LatencyConfig,
    ChatCompletionLatency,
    CompletionLatency,
    EmbeddingLatency,
)
import pytest
import requests

from .test_uvicorn_server import UvicornTestServer

from aoai_api_simulator.record_replay.handler import get_default_forwarders

API_KEY = "123456789"


def _get_config(extension_path: str) -> Config:
    config = Config(generators=get_default_generators())
    config.simulator_api_key = API_KEY
    config.simulator_mode = "generate"
    config.recording.forwarders = get_default_forwarders()
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
    config.extension_path = extension_path
    initialize_config(config)
    return config


@pytest.mark.asyncio
async def test_load_extension_from_single_file():
    """
    Ensure we can load a single file extension
    """

    config = _get_config(extension_path="examples/generator_echo/generator_config.py")

    # Check that the generator is called
    server = UvicornTestServer(config)
    with server.run_in_thread():
        response = requests.post(
            "http://localhost:8001/echo",
            timeout=10,
            data="hello",
            headers={"api-key": API_KEY},
        )
        assert response.status_code == 200
        assert response.text == "Echo: hello"


@pytest.mark.asyncio
async def test_load_extension_from_directory():
    """
    Ensure we can load a single file extension
    """

    config = _get_config(extension_path="examples/forwarder_doc_intelligence")

    assert config.recording.forwarders[-1].__name__ == "forward_to_azure_document_intelligence"


@pytest.mark.asyncio
async def test_load_extension_from_directory_init_py():
    """
    Ensure we can load a single file extension
    """

    config = _get_config(extension_path="examples/forwarder_doc_intelligence/__init__.py")

    assert config.recording.forwarders[-1].__name__ == "forward_to_azure_document_intelligence"
