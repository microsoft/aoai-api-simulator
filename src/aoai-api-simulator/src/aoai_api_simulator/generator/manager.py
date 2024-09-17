import inspect
import logging
from typing import Awaitable, Callable

from aoai_api_simulator.models import RequestContext
from fastapi import HTTPException, Response

from .openai import (
    azure_openai_chat_completion,
    azure_openai_completion,
    azure_openai_embedding,
    azure_openai_translation,
)

logger = logging.getLogger(__name__)


def get_default_generators() -> list[Callable[[RequestContext], Response | Awaitable[Response] | None]]:
    return [
        azure_openai_embedding,
        azure_openai_completion,
        azure_openai_chat_completion,
        azure_openai_translation,
    ]


async def invoke_generators(
    context: RequestContext, generators: list[Callable[[RequestContext], Response | Awaitable[Response] | None]]
):
    for generator in generators:
        try:
            response = generator(context=context)
            if response is not None and inspect.isawaitable(response):
                response = await response
            if response is not None:
                return response
        except HTTPException as he:
            raise he  # pass through
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "Error generating response (name='%s', request='%s')",
                generator.__name__,
                context.request.url,
                exc_info=e,
            )
    return None
