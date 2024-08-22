"""
Provides the UvicornTestServer class for in-proc testing of the simulator API
"""

import contextlib
import logging
import threading
import time
import pytest
import requests
import uvicorn

from aoai_api_simulator.app_builder import app, apply_config
from aoai_api_simulator.config_loader import set_config
from aoai_api_simulator.models import (
    Config,
    LatencyConfig,
    ChatCompletionLatency,
    CompletionLatency,
    EmbeddingLatency,
)

logger = logging.getLogger("tests")


class UvicornTestServer(uvicorn.Server):
    """
    A subclass of Uvicorn's Server class that allows running the server in a separate thread
    to enable running the server in-process during tests
    """

    def __init__(self, config: Config):
        set_config(config)
        apply_config()
        uvconfig = uvicorn.Config(app, host="127.0.0.1", port=8001, loop="asyncio")

        super().__init__(uvconfig)
        self.started = False
        self.should_exit = False

    @contextlib.contextmanager
    def run_in_thread(self):
        """
        Run the server in a separate thread
        (based on https://github.com/encode/uvicorn/discussions/1103#discussioncomment-941726)
        """
        thread = threading.Thread(target=self.run)
        thread.start()
        try:
            while not self.started:
                time.sleep(1e-3)
            yield
        finally:
            self.should_exit = True
            thread.join()


@pytest.mark.asyncio
async def test_root_message():
    # This mostly validates that the UvicornTestServer starts up the simulator :-)

    config = Config(generators=[])
    config.simulator_mode = "generate"
    config.simulator_api_key = "123456789"
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

    server = UvicornTestServer(config)
    with server.run_in_thread():
        response = requests.get("http://localhost:8001/", timeout=10)
        assert response.status_code == 200
        assert b"aoai-api-simulator is running" in response.content
