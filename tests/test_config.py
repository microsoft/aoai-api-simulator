"""
Test simulator config endpoints
"""

from openai import AzureOpenAI, InternalServerError
import pytest
from pytest_httpserver import HTTPServer
import requests

from tests.test_openai_record import TempDirectory

from .test_uvicorn_server import UvicornTestServer

from aoai_api_simulator.generator.manager import get_default_generators
from aoai_api_simulator.models import (
    Config,
    LatencyConfig,
    ChatCompletionLatency,
    CompletionLatency,
    EmbeddingLatency,
)
from aoai_api_simulator.record_replay.handler import get_default_forwarders

API_KEY = "123456789"


def _get_generator_config() -> Config:
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
    return config


@pytest.mark.asyncio
async def test_config_update_latency():
    """
    Ensure that a latency value can be updated
    """
    config = _get_generator_config()
    server = UvicornTestServer(config)
    with server.run_in_thread():
        url = "http://localhost:8001/++/config"
        headers = {"api-key": "123456789"}

        response = requests.get(
            url,
            headers=headers,
            timeout=10,
        )
        config_json = response.json()

        # Assert initial values
        assert config_json["simulator_mode"] == "generate"
        assert config_json["latency"]["open_ai_completions"]["mean"] == 0
        assert config_json["latency"]["open_ai_completions"]["std_dev"] == 0.1
        assert config_json["latency"]["open_ai_chat_completions"]["mean"] == 0
        assert config_json["latency"]["open_ai_chat_completions"]["std_dev"] == 0.1

        config_update = {
            "latency": {
                "open_ai_completions": {
                    "mean": 0.5,
                }
            }
        }
        response = requests.patch(
            "http://localhost:8001/++/config",
            headers=headers,
            json=config_update,
            timeout=10,
        )
        config_json = response.json()

        # Assert updated values to ensure change was applied
        # and unchanged values remain
        assert config_json["simulator_mode"] == "generate"
        assert config_json["latency"]["open_ai_completions"]["mean"] == 0.5
        assert config_json["latency"]["open_ai_completions"]["std_dev"] == 0.1
        assert config_json["latency"]["open_ai_chat_completions"]["mean"] == 0
        assert config_json["latency"]["open_ai_chat_completions"]["std_dev"] == 0.1


def _get_record_config(httpserver: HTTPServer, recording_path: str) -> Config:
    forwarding_server_url = httpserver.url_for("/").removesuffix("/")
    config = Config(generators=[])
    config.simulator_api_key = API_KEY
    config.simulator_mode = "record"
    config.recording.aoai_api_endpoint = forwarding_server_url
    config.recording.aoai_api_key = "123456789"
    config.recording.dir = recording_path
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
    return config


@pytest.mark.asyncio
async def test_openai_record_replay_completion_via_config_endpoint(httpserver: HTTPServer):
    """
    Ensure we can call the completion endpoint using the record mode
    and then use the config endpoint to switch to replay mode
    """

    # Set up pytest-httpserver to provide an endpoint for the simulator
    # to call in record mode
    httpserver.expect_request(
        uri="/openai/deployments/deployment1/completions",
        query_string="api-version=2023-12-01-preview",
        method="POST",
    ).respond_with_data(
        '{"id":"cmpl-95FbXadIqJEMZZ1Rl0chTcKRxk2ez","object":"text_completion","created":1711038651,"model":"gpt-35-turbo","prompt_filter_results":[{"prompt_index":0,"content_filter_results":{"hate":{"filtered":false,"severity":"safe"},"self_harm":{"filtered":false,"severity":"safe"},"sexual":{"filtered":false,"severity":"safe"},"violence":{"filtered":false,"severity":"safe"}}}],"choices":[{"text":"This is a test","index":0,"finish_reason":"length","logprobs":null,"content_filter_results":{"hate":{"filtered":false,"severity":"safe"},"self_harm":{"filtered":false,"severity":"safe"},"sexual":{"filtered":false,"severity":"safe"},"violence":{"filtered":false,"severity":"safe"}}}],"usage":{"prompt_tokens":7,"completion_tokens":50,"total_tokens":57}}\n'
    )
    httpserver.expect_request("/hello").respond_with_data("Hello, world!")

    with TempDirectory() as temp_dir:
        config = _get_record_config(httpserver, temp_dir.path)
        server = UvicornTestServer(config)
        with server.run_in_thread():
            aoai_client = AzureOpenAI(
                api_key=API_KEY,
                api_version="2023-12-01-preview",
                azure_endpoint="http://localhost:8001",
                max_retries=0,
            )

            # Make call in record more
            prompt = "This is a test prompt"
            response = aoai_client.completions.create(model="deployment1", prompt=prompt, max_tokens=50)
            assert len(response.choices) == 1
            assert response.choices[0].text == "This is a test"

            # Undo httpserver config to ensure there isn't an endpoint to forward to
            # when testing in replay mode
            httpserver.clear_all_handlers()

            # Use the config endpoint to switch to replay mode

            # Repeated request from above should succeed
            prompt = "This is a test prompt"
            response = aoai_client.completions.create(model="deployment1", prompt=prompt, max_tokens=50)
            assert len(response.choices) == 1
            assert response.choices[0].text == "This is a test"

            # this call should fail
            with pytest.raises(InternalServerError) as e:
                prompt = "This is a different prompt value and should fail as it isn't in the recording file"
                response = aoai_client.completions.create(model="deployment1", prompt=prompt, max_tokens=50)

            assert e.value.status_code == 500
