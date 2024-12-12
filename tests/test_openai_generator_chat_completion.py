"""
Test the OpenAI generator endpoints
"""

import collections.abc
import json

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
from pydantic import BaseModel

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
        "gpt-4-10m": OpenAIDeployment(
            name="gpt-4-10m",
            model=model_catalogue["gpt-4"],
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


@pytest.mark.asyncio
async def test_response_format_not_present_gives_plain_text():
    """
    Ensure responses without a response_format in the request default to plain text
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
        response = aoai_client.chat.completions.create(model="gpt-4-10m", messages=messages, max_tokens=max_tokens)

        assert len(response.choices) == 1
        assert len(response.choices[0].message.content) > 20
        assert response.choices[0].message.content[0] != "{"


@pytest.mark.asyncio
async def test_response_format_text_gives_plain_text():
    """
    Ensure responses with response_format of "text" in the request return plain text
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
        response = aoai_client.chat.completions.create(model="gpt-4-10m", messages=messages, max_tokens=max_tokens)

        assert len(response.choices) == 1
        assert len(response.choices[0].message.content) > 20
        assert response.choices[0].message.content[0] != "{"


@pytest.mark.asyncio
async def test_response_format_invalid_schema_gives_error():
    """
    Ensure responses with response_format of "something_invalid" in the request get an error response
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
        with pytest.raises(BadRequestError) as e:
            aoai_client.chat.completions.create(
                model="gpt-4-10m",
                messages=messages,
                max_tokens=1000,
                response_format={
                    "type": "something_invalid",
                },
            )

        assert e.value.status_code == 400
        assert "Unsupported response_format type: something_invalid" in e.value.message


@pytest.mark.asyncio
async def test_response_format_json_schema_gives_json_pydantic():
    """
    Ensure responses with response_format of "json_schema" in the request return json
    using the OpenAI SDK pydantic helpers
    """

    class CalendarEvent(BaseModel):
        name: str
        date: str
        participants: list[str]

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
        response = aoai_client.beta.chat.completions.parse(
            model="gpt-4-10m", messages=messages, max_tokens=1000, response_format=CalendarEvent
        )

        assert len(response.choices) == 1
        assert len(response.choices[0].message.content) > 20
        assert response.choices[0].message.content[0] == "{", "expected json response"
        assert response.choices[0].message.parsed is not None
        assert isinstance(response.choices[0].message.parsed.name, str)
        assert isinstance(response.choices[0].message.parsed.date, str)
        assert not isinstance(response.choices[0].message.parsed.participants, str)
        assert isinstance(response.choices[0].message.parsed.participants, collections.abc.Sequence)


@pytest.mark.asyncio
async def test_response_format_json_schema_gives_json_manual():
    """
    Ensure responses with response_format of "json_schema" in the request return json
    using manual schema specification
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
        response = aoai_client.chat.completions.create(
            model="gpt-4-10m",
            messages=messages,
            max_tokens=1000,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "date": {"type": "string"},
                            "participants": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["name", "date", "participants"],
                        "additionalProperties": False,
                    },
                },
            },
        )

        assert len(response.choices) == 1
        assert len(response.choices[0].message.content) > 20
        assert response.choices[0].message.content[0] == "{", "expected json response"
        json_content = json.loads(response.choices[0].message.content)
        assert isinstance(json_content["name"], str)
        assert isinstance(json_content["date"], str)
        assert not isinstance(json_content["participants"], str)
        assert isinstance(json_content["participants"], collections.abc.Sequence)


@pytest.mark.asyncio
async def test_response_format_json_schema_with_invalid_model_gives_error():
    """
    Ensure json_schema isn't used with models that don't support it
    """

    class CalendarEvent(BaseModel):
        name: str
        date: str
        participants: list[str]

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
            aoai_client.beta.chat.completions.parse(
                # Use GPT 3.5 which doesn't support json_schema
                model="gpt-3.5-10m",
                messages=messages,
                max_tokens=1000,
                response_format=CalendarEvent,
            )

        assert e.value.status_code == 400
        assert "'response_format' of type 'json_schema' is not supported with this model" in e.value.message


@pytest.mark.asyncio
async def test_response_format_json_schema_with_jsf_provider_gives_error():
    """
    Ensure responses with a schema using the $provider hints in JSF are rejected.
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
        with pytest.raises(BadRequestError) as e:
            aoai_client.chat.completions.create(
                model="gpt-4-10m",
                messages=messages,
                max_tokens=1000,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "$provider": "faker.name"},
                                "date": {"type": "string"},
                                "participants": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["name", "date", "participants"],
                            "additionalProperties": False,
                        },
                    },
                },
            )

        assert e.value.status_code == 400
        assert "$provider is not allowed in JSON Schema" in e.value.message
