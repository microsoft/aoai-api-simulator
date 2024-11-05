import inspect
import json
import logging
import math
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from aoai_api_simulator import constants
from aoai_api_simulator.metrics import simulator_metrics
from aoai_api_simulator.models import (
    Config,
    OpenAIDeployment,
    RequestContext,
)
from fastapi import Response

logger = logging.getLogger(__name__)


async def apply_limits(context: RequestContext, response: Response) -> Awaitable[Response]:
    limiter_name = context.values.get(constants.SIMULATOR_KEY_LIMITER)
    limiter = context.config.limiters.get(limiter_name) if limiter_name else None
    if limiter:
        limit_response = limiter(context, response)
        if limit_response and inspect.isawaitable(limit_response):
            limit_response = await limit_response
        return limit_response

    logger.info("No limiter found for response: %s [limiter name: %s]", context.request.url.path, limiter_name)
    return response


def no_op_limiter(_: RequestContext, response: Response) -> None:
    return response


deployment_warnings_issues: dict[str, bool] = {}


async def determine_token_cost(context: RequestContext):
    operation_name = context.values.get(constants.SIMULATOR_KEY_OPERATION_NAME)
    if operation_name is None:
        logger.info("No operation name found in context for request: %s", context.request.url.path)
        return 0

    if operation_name == constants.OPENAI_OPERATION_TRANSLATION:
        # Don't apply token limits to translations
        # Also, don't read the body as it may be a stream
        return 0

    # Check whether the request has set max_tokens
    # If so, use that as the rate-limiting token value
    request_body = await context.request.json()
    max_tokens = request_body.get("max_tokens")
    if max_tokens:
        token_cost = max_tokens
    else:
        # otherwise, calculate the rate-limiting token cost

        # TODO: update this to enable plugging in different behaviour for different models
        # This behaviour works for PAYG with the following models
        #  - text-embedding-ada-002
        #  - text-embedding-3-small
        #  - text-embedding-3-large
        #  - gpt-3.5-turbo

        operation_name = context.values.get(constants.SIMULATOR_KEY_OPERATION_NAME)

        if operation_name == constants.OPENAI_OPERATION_CHAT_COMPLETIONS:
            token_cost = 16
        elif operation_name == constants.OPENAI_OPERATION_COMPLETIONS:
            token_cost = 16
        elif operation_name == constants.OPENAI_OPERATION_EMBEDDINGS:
            request_body = await context.request.json()
            request_input = request_body.get("input")
            if request_input is None:
                logger.warning("openai_limiter: input not found in request body for embedding request")
                token_cost = 0
            else:
                if isinstance(request_input, list):
                    # TODO - validate whether we should sum the ceil values or ceil the sum
                    token_cost = sum(math.ceil(len(input_str) / 4) for input_str in request_input)
                else:
                    token_cost = math.ceil(len(request_input) / 4)
        else:
            # TODO: implement calculations for other endpoints
            logger.warning(
                "openai_limiter: unhanndled endpoint %s (operation_name: %s)", context.request.url.path, operation_name
            )
            token_cost = 0

    context.values[constants.SIMULATOR_KEY_OPENAI_RATE_LIMIT_TOKENS] = token_cost
    return token_cost


@dataclass
class WindowEntry:
    timestamp: float
    token_cost: int


@dataclass
class WindowAddResult:
    success: bool
    remaining_tokens: int | None
    remaining_requests: int | None
    retry_after: int | None
    retry_reason: str | None  # "tokens" or "requests"


# pylint: disable-next=too-few-public-methods
class TokensPerMinuteSlidingWindow:
    """
    Represents a time window for rate-limiting based on tokens-per-minute and requests-per-10-seconds
    """

    _requests: list[WindowEntry]
    _requests_per_10_seconds: int
    _tokens_per_minute: int

    def __init__(self, requests_per_10_seconds: int, tokens_per_minute: int):
        self._requests_per_10_seconds = requests_per_10_seconds
        self._tokens_per_minute = tokens_per_minute
        self._requests = []

    def _purge(self, cut_off: float):
        while len(self._requests) > 0 and self._requests[0].timestamp <= cut_off:
            self._requests.pop(0)

    def _calculate_window_counts_for_request(self, token_cost: int, timestamp: float) -> tuple[int, int, float, float]:
        # Iterate the the list in reverse order
        # Track:
        #  - the number of requests in the last 10 seconds (including this request)
        #  - the number of tokens in the last 60 seconds (including this request)
        #  - the time when we have requests_per_10_seconds requests (including this request)
        #  - the time when we have tokens_per_minute tokens (including this request)

        request_count_in_10s = 1
        token_count_in_60s = token_cost
        requests_count = 1
        tokens_count = token_cost
        requests_full_time = -math.inf
        tokens_full_time = -math.inf
        for i in range(len(self._requests) - 1, -1, -1):
            request = self._requests[i]

            if requests_count <= self._requests_per_10_seconds:
                requests_count += 1

            if tokens_count <= self._tokens_per_minute:
                tokens_count += request.token_cost

            if requests_full_time == -math.inf and requests_count > self._requests_per_10_seconds:
                # we're full at the last request
                # so have space once this request expires
                requests_full_time = self._requests[i].timestamp
            if tokens_full_time == -math.inf and tokens_count > self._tokens_per_minute:
                # we're full at the last request
                # so have space once this request expires
                tokens_full_time = self._requests[i].timestamp

            if request.timestamp > timestamp - 10:
                request_count_in_10s += 1
            # if request.timestamp > timestamp - 60:
            # all the requests are in the last 60s (as we purged any that are older)
            token_count_in_60s += request.token_cost

        return request_count_in_10s, token_count_in_60s, requests_full_time, tokens_full_time

    def add_request(self, token_cost: int, timestamp: float = -1) -> WindowAddResult:
        """
        Add a request to the window
        """
        if timestamp == -1:
            timestamp = time.time()

        # remove items older than a minute
        self._purge(timestamp - 60)

        request_count_in_10s, token_count_in_60s, requests_full_time, tokens_full_time = (
            self._calculate_window_counts_for_request(token_cost=token_cost, timestamp=timestamp)
        )

        # If requests_full_duration is less than 10 then we need less than 10 seconds of history
        # to exceed the requests_per_10_seconds limit, i.e. we already used the limit for the current 10s window
        # If tokens_full_duration is less than 60 then we need less than 60 seconds of history
        # to exceed the tokens_per_minute limit, i.e. we already used the limit for the current 60s window
        # if requests_full_duration < 10 or tokens_full_duration < 60:
        if token_count_in_60s > self._tokens_per_minute or request_count_in_10s > self._requests_per_10_seconds:
            # Edge case where we've hit the max tokens and the current request is for max_tokens
            # but haven't hit the request limit
            # in this case, we wait until the last saved request is out of the window
            if (
                token_cost == self._tokens_per_minute
                and requests_full_time == -math.inf
                and tokens_full_time == -math.inf
            ):
                tokens_full_time = self._requests[-1].timestamp

            # calculate the duration to have a full request count
            requests_full_duration = timestamp - requests_full_time
            # calculate the duration to have a full token count
            tokens_full_duration = timestamp - tokens_full_time

            time_to_reset_requests = 10 - requests_full_duration
            time_to_reset_tokens = 60 - tokens_full_duration

            if time_to_reset_requests > time_to_reset_tokens:
                reason = "requests"
                retry_after = math.ceil(time_to_reset_requests)
                if time_to_reset_requests <= 0:
                    raise ValueError("time_to_reset_requests should be greater than 0")
            else:
                reason = "tokens"
                retry_after = math.ceil(time_to_reset_tokens)
                if time_to_reset_tokens <= 0:
                    raise ValueError("time_to_reset_tokens should be greater than 0")

            return WindowAddResult(
                success=False,
                retry_after=retry_after,
                retry_reason=reason,
                remaining_tokens=None,
                remaining_requests=None,
            )

        # We have enough capacity to add the request
        self._requests.append(WindowEntry(timestamp, token_cost))
        # token_count_in_60s += token_cost
        # request_count_in_10s += 1
        return WindowAddResult(
            success=True,
            retry_after=None,
            retry_reason=None,
            remaining_tokens=self._tokens_per_minute - token_count_in_60s,
            remaining_requests=self._requests_per_10_seconds - request_count_in_10s,
        )


# pylint: disable-next=too-few-public-methods
class RequestsPerMinuteSlidingWindow:
    """
    Represents a time window for rate-limiting based on requests-per-minute
    """

    _requests: list[WindowEntry]
    _requests_per_minute: int

    def __init__(self, requests_per_minute: int):
        self._requests_per_minute = requests_per_minute
        self._requests = []

    def _purge(self, cut_off: float):
        while len(self._requests) > 0 and self._requests[0].timestamp <= cut_off:
            self._requests.pop(0)

    def add_request(self, timestamp: float = -1) -> WindowAddResult:
        """
        Add a request to the window
        """

        if timestamp == -1:
            timestamp = time.time()

        # remove items older than a minute
        self._purge(timestamp - 60)

        if len(self._requests) >= self._requests_per_minute:
            return WindowAddResult(
                success=False,
                retry_after=math.ceil(60 - (timestamp - self._requests[0].timestamp)),
                retry_reason="requests",
                remaining_tokens=None,
                remaining_requests=None,
            )

        self._requests.append(WindowEntry(timestamp, 0))
        return WindowAddResult(
            success=True,
            retry_after=None,
            retry_reason=None,
            remaining_requests=self._requests_per_minute - len(self._requests),
            remaining_tokens=None,
        )


def create_openai_tokens_limiter(
    deployments: dict[str, OpenAIDeployment],
) -> Callable[[RequestContext, Response], Response | None]:
    # dict of TokensPerMinuteSlidingWindow objects keyed on deployment name
    deployment_limits: dict[str, TokensPerMinuteSlidingWindow] = {}

    for deployment in deployments.values():
        # only handle token-based limited models
        if deployment.model.is_token_limited:
            tokens_per_minute = deployment.tokens_per_minute
            requests_per_10s = math.ceil(tokens_per_minute / 1000)  # 1/6 * (6 * TPM / 1000)
            deployment_limits[deployment.name] = TokensPerMinuteSlidingWindow(
                requests_per_10_seconds=requests_per_10s, tokens_per_minute=tokens_per_minute
            )

    async def limiter(context: RequestContext, response: Response) -> Awaitable[Response]:
        deployment_name = context.values.get(constants.SIMULATOR_KEY_DEPLOYMENT_NAME)
        if not deployment_name:
            logger.warning("openai_limiter: deployment name not found in context")

        window: TokensPerMinuteSlidingWindow = deployment_limits.get(deployment_name)
        if not window:
            if not deployment_warnings_issues.get(deployment_name):
                logger.warning("Deployment %s not found in limiters - not applying rate limits", deployment_name)
                deployment_warnings_issues[deployment_name] = True
            return response

        token_cost = await determine_token_cost(context)
        window_result = window.add_request(token_cost=token_cost)
        if not window_result.success:
            cost = token_cost if window_result.retry_reason == "tokens" else 1
            simulator_metrics.histogram_rate_limit.record(
                cost,
                attributes={
                    "deployment": deployment_name,
                    "reason": window_result.retry_reason,
                },
            )

            content = {
                "error": {
                    "code": "429",
                    "message": "Requests to the OpenAI API Simulator have exceeded call rate limit. "
                    + f"Please retry after {window_result.retry_after} seconds.",
                }
            }

            retry_after_header = (
                "x-ratelimit-reset-tokens" if window_result.retry_reason == "tokens" else "x-ratelimit-reset-requests"
            )
            return Response(
                status_code=429,
                content=json.dumps(content),
                headers={
                    "Retry-After": str(window_result.retry_after),
                    retry_after_header: str(window_result.retry_after),
                },
            )
        response.headers["x-ratelimit-remaining-tokens"] = str(window_result.remaining_tokens)
        response.headers["x-ratelimit-remaining-requests"] = str(window_result.remaining_requests)
        return response

    return limiter


def create_openai_requests_limiter(
    deployments: dict[str, OpenAIDeployment],
) -> Callable[[RequestContext, Response], Response | None]:
    # dict of RequestsPerMinuteSlidingWindow objects keyed on deployment name
    deployment_limits: dict[str, RequestsPerMinuteSlidingWindow] = {}

    for deployment in deployments.values():
        # only handle request-based limited models
        if not deployment.model.is_token_limited:
            requests_per_minute = deployment.requests_per_minute
            deployment_limits[deployment.name] = RequestsPerMinuteSlidingWindow(requests_per_minute)

    async def limiter(context: RequestContext, response: Response) -> Awaitable[Response]:
        deployment_name = context.values.get(constants.SIMULATOR_KEY_DEPLOYMENT_NAME)
        if not deployment_name:
            logger.warning("openai_limiter: deployment name not found in context")

        window: RequestsPerMinuteSlidingWindow = deployment_limits.get(deployment_name)
        if not window:
            if not deployment_warnings_issues.get(deployment_name):
                logger.warning("Deployment %s not found in limiters - not applying rate limits", deployment_name)
                deployment_warnings_issues[deployment_name] = True
            return response

        window_result = window.add_request()
        if not window_result.success:
            simulator_metrics.histogram_rate_limit.record(
                1,
                attributes={
                    "deployment": deployment_name,
                    "reason": window_result.retry_reason,
                },
            )

            content = {
                "error": {
                    "code": "429",
                    "message": "Requests to the OpenAI API Simulator have exceeded call rate limit. "
                    + f"Please retry after {window_result.retry_after} seconds.",
                }
            }

            return Response(
                status_code=429,
                content=json.dumps(content),
                headers={
                    "Retry-After": str(window_result.retry_after),
                },
            )
        response.headers["x-ratelimit-remaining-requests"] = str(window_result.remaining_requests)
        return response

    return limiter


def get_default_limiters(config: Config):
    # Dictionary of limiters keyed by name
    # Each limiter is a function that takes a response and returns a boolean indicating
    # whether the request should be allowed
    # Limiter returns Response object if request should be blocked or None otherwise
    return {
        constants.LIMITER_OPENAI_TOKENS: create_openai_tokens_limiter(config.openai_deployments or {}),
        constants.LIMITER_OPENAI_REQUESTS: create_openai_requests_limiter(config.openai_deployments or {}),
    }
