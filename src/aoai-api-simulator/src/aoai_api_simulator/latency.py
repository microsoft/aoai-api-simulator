import asyncio
import time

from aoai_api_simulator import constants
from aoai_api_simulator.metrics import simulator_metrics
from aoai_api_simulator.models import RequestContext
from fastapi import Response


class LatencyGenerator:
    """
    LatencyGenerator is a context manager that adds simulated latency to the response.
    The latency added is based on the context.values[TARGET_DURATION_MS] value.
    Additionaly, the generator emits metrics for the response (base latency and added latency).
    """

    __context: RequestContext
    __start_time: float
    __response: Response | None

    def __init__(self, context: RequestContext):
        self.__context = context
        self.__response = None

    def set_response(self, response: Response):
        self.__response = response

    async def __aenter__(self):
        self.__start_time = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.apply_latency()

    async def apply_latency(self):
        """Apply additional latency to the request if required"""

        if not self.__response:
            # if we haven't been assigned a response, skip adding latency and emitting metrics
            return

        extra_latency_s = 0
        base_end_time = time.perf_counter()
        base_duration_s = base_end_time - self.__start_time

        deployment_name = self.__context.values.get(constants.SIMULATOR_KEY_DEPLOYMENT_NAME)
        prompt_tokens_used = self.__context.values.get(constants.SIMULATOR_KEY_OPENAI_PROMPT_TOKENS, 0)
        completion_tokens_used = self.__context.values.get(constants.SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS, 0)
        rate_limit_tokens = self.__context.values.get(constants.SIMULATOR_KEY_OPENAI_RATE_LIMIT_TOKENS, 0)

        status_code = self.__response.status_code
        if status_code < 300:
            target_duration_ms = self.__context.values.get(constants.TARGET_DURATION_MS, None)
            if target_duration_ms:
                target_duration_s = target_duration_ms / 1000
                extra_latency_s = target_duration_s - base_duration_s

        if extra_latency_s and extra_latency_s > 0:
            await asyncio.sleep(extra_latency_s)

        full_end_time = time.perf_counter()
        simulator_metrics.histogram_latency_base.record(
            base_duration_s,
            attributes={
                "status_code": status_code,
                "deployment": deployment_name,
            },
        )
        simulator_metrics.histogram_latency_full.record(
            (full_end_time - self.__start_time),
            attributes={
                "status_code": status_code,
                "deployment": deployment_name,
            },
        )

        # Token metrics
        if prompt_tokens_used > 0:
            simulator_metrics.histogram_tokens_requested.record(
                prompt_tokens_used,
                attributes={
                    "deployment": deployment_name,
                    "token_type": "prompt",
                },
            )
        if completion_tokens_used > 0:
            simulator_metrics.histogram_tokens_requested.record(
                completion_tokens_used,
                attributes={
                    "deployment": deployment_name,
                    "token_type": "completion",
                },
            )

        if status_code < 300:
            # only track tokens used for successful requests
            if prompt_tokens_used > 0:
                simulator_metrics.histogram_tokens_used.record(
                    prompt_tokens_used,
                    attributes={
                        "deployment": deployment_name,
                        "token_type": "prompt",
                    },
                )
            if completion_tokens_used > 0:
                simulator_metrics.histogram_tokens_used.record(
                    completion_tokens_used,
                    attributes={
                        "deployment": deployment_name,
                        "token_type": "completion",
                    },
                )
            if rate_limit_tokens > 0:
                simulator_metrics.histogram_tokens_rate_limit.record(
                    rate_limit_tokens,
                    attributes={
                        "deployment": deployment_name,
                    },
                )
