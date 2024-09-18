import random
from dataclasses import dataclass
from typing import Annotated, Awaitable, Callable

import nanoid

# from aoai_api_simulator.pipeline import RequestContext
from fastapi import Request, Response
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests import Response as requests_Response
from starlette.routing import Match, Route


class RequestContext:
    _config: "Config"
    _request: Request
    _values: dict[str, any]

    def __init__(self, config: "Config", request: Request):
        self._config = config
        self._request = request
        self._values = {}

    @property
    def config(self) -> "Config":
        return self._config

    @property
    def request(self) -> Request:
        return self._request

    @property
    def values(self) -> dict[str, any]:
        return self._values

    def _strip_path_query(self, path: str) -> str:
        query_start = path.find("?")
        if query_start != -1:
            path = path[:query_start]
        return path

    def is_route_match(self, request: Request, path: str, methods: list[str]) -> tuple[bool, dict]:
        """
        Checks if a given route matches the provided request.

        Args:
                route (Route): The route to check against.
                request (Request): The request to match.

        Returns:
                tuple[bool, dict]: A tuple containing a boolean indicating whether the route matches the request,
                and a dictionary of path parameters if the match is successful.
        """

        route = Route(path=path, methods=methods, endpoint=_endpoint)
        path_to_match = self._strip_path_query(request.url.path)
        match, scopes = route.matches({"type": "http", "method": request.method, "path": path_to_match})
        if match != Match.FULL:
            return (False, {})
        return (True, scopes["path_params"])


class RecordingConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    dir: str = Field(default=".recording", alias="RECORDING_DIR")
    autosave: bool = Field(default=True, alias="RECORDING_AUTOSAVE")
    aoai_api_key: str | None = Field(default=None, alias="AZURE_OPENAI_KEY")
    aoai_api_endpoint: str | None = Field(default=None, alias="AZURE_OPENAI_ENDPOINT")
    forwarders: (
        list[
            Callable[
                [RequestContext],
                Response
                | Awaitable[Response]
                | requests_Response
                | Awaitable[requests_Response]
                | dict
                | Awaitable[dict]
                | None,
            ]
        ]
        | None
    ) = []


class CompletionLatency(BaseSettings):
    mean: float = Field(default=15, alias="LATENCY_OPENAI_COMPLETIONS_MEAN")
    std_dev: float = Field(default=2, alias="LATENCY_OPENAI_COMPLETIONS_STD_DEV")

    def get_value(self) -> float:
        return random.normalvariate(self.mean, self.std_dev)


class ChatCompletionLatency(BaseSettings):
    mean: float = Field(default=19, alias="LATENCY_OPENAI_CHAT_COMPLETIONS_MEAN")
    std_dev: float = Field(default=6, alias="LATENCY_OPENAI_CHAT_COMPLETIONS_STD_DEV")

    def get_value(self) -> float:
        return random.normalvariate(self.mean, self.std_dev)


class EmbeddingLatency(BaseSettings):
    mean: float = Field(default=100, alias="LATENCY_OPENAI_EMBEDDINGS_MEAN")
    std_dev: float = Field(default=30, alias="LATENCY_OPENAI_EMBEDDINGS_STD_DEV")

    def get_value(self) -> float:
        return random.normalvariate(self.mean, self.std_dev)


class LatencyConfig(BaseSettings):
    """
    Defines the latency for different types of requests

    open_ai_embeddings: the latency for OpenAI embeddings - mean is mean request duration in milliseconds
    open_ai_completions: the latency for OpenAI completions - mean is the number of milliseconds per token
    open_ai_chat_completions: the latency for OpenAI chat completions - mean is the number of milliseconds per token
    """

    open_ai_completions: CompletionLatency = Field(default=CompletionLatency())
    open_ai_chat_completions: ChatCompletionLatency = Field(default=ChatCompletionLatency())
    open_ai_embeddings: EmbeddingLatency = Field(default=EmbeddingLatency())


class PatchableConfig(BaseSettings):
    simulator_mode: str = Field(default="generate", alias="SIMULATOR_MODE", pattern="^(generate|record|replay)$")
    simulator_api_key: str = Field(default="", alias="SIMULATOR_API_KEY")
    recording: RecordingConfig = Field(default=RecordingConfig())
    openai_deployments: dict[str, "OpenAIDeployment"] | None = Field(default=None)
    latency: Annotated[LatencyConfig, Field(default=LatencyConfig())]
    allow_undefined_openai_deployments: bool = Field(default=True, alias="ALLOW_UNDEFINED_OPENAI_DEPLOYMENTS")

    # Disable all the no-self-argument violations in this function
    # pylint: disable=no-self-argument
    @field_validator("simulator_api_key")
    def simulator_api_key_should_not_be_empty_string(cls, v):
        if v == "":
            return nanoid.generate(size=30)
        return v

    # pylint: enable=no-self-argument


class Config(PatchableConfig):
    """
    Configuration for the simulator
    """

    generators: list[Callable[[RequestContext], Response | Awaitable[Response] | None]] = None
    limiters: dict[str, Callable[[RequestContext, Response], Response | None]] = {}
    extension_path: Annotated[str | None, Field(default=None, alias="EXTENSION_PATH")]


@dataclass
class OpenAIModel:
    name: str


@dataclass
class OpenAIChatModel(OpenAIModel):
    pass


@dataclass
class OpenAIEmbeddingModel(OpenAIModel):
    name: str
    supports_custom_dimensions: bool


@dataclass
class OpenAIDeployment:
    name: str
    model: OpenAIModel
    tokens_per_minute: int = 0
    embedding_size: int = 0


# re-using Starlette's Route class to define a route
# endpoint to pass to Route
def _endpoint():
    pass
