import json
import logging
import os
import time
from typing import Callable
from aoai_api_simulator.limiters import no_op_limiter
from fastapi import Response
from limits import storage, strategies, RateLimitItemPerSecond

from aoai_api_simulator.models import Config, RequestContext

from .doc_intell import doc_intelligence_analyze, doc_intelligence_analyze_result

logger = logging.getLogger(__name__)


doc_intelligence_rps: int = int(os.getenv("DOC_INTELLIGENCE_RPS", "15"))
logger.info("📝 Using Doc Intelligence RPS: %s", doc_intelligence_rps)


memory_storage = storage.MemoryStorage()


def initialize(config: Config):
    """initialize is the entry point invoked by the simulator"""

    # Add the generators to the config if not already present
    # (NOTE: initialize may be called multiple times)
    if doc_intelligence_analyze not in config.generators:
        config.generators.append(doc_intelligence_analyze)
        config.generators.append(doc_intelligence_analyze_result)

    config.limiters["docintelligence"] = create_doc_intelligence_limiter(
        memory_storage, requests_per_second=doc_intelligence_rps
    )


def create_doc_intelligence_limiter(
    limit_storage: storage.Storage, requests_per_second: int
) -> Callable[[RequestContext, Response], Response]:
    """
    Create a rate limiter for the Doc Intelligence generator.
    A rate limiter is a function that takes a RequestContext and Response and returns a Response or None.
    If a Response is returned, it will be used as the response to the request in place of the original response.
    """

    moving_window = strategies.MovingWindowRateLimiter(limit_storage)
    limit = RateLimitItemPerSecond(requests_per_second, 1)

    if requests_per_second <= 0:
        return no_op_limiter

    def limiter(_: RequestContext, response: Response) -> Response | None:
        if not moving_window.hit(limit):
            stats = moving_window.get_window_stats(limit)
            current_time = int(time.time())
            retry_after = str(stats.reset_time - current_time)
            content = {
                "error": {
                    "code": "429",
                    "message": "Requests to the Doc Intelligence API Simulator have exceeded call rate limit. "
                    + f"Please retry after {retry_after} seconds.",
                }
            }
            return Response(
                status_code=429,
                content=json.dumps(content),
                headers={"Retry-After": retry_after, "x-ratelimit-reset-requests": retry_after},
            )
        return response

    return limiter
