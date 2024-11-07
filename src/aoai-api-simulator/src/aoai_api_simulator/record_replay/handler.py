import inspect
import logging
import time
from typing import Awaitable, Callable

import fastapi
import requests
from aoai_api_simulator import constants
from aoai_api_simulator.models import RequestContext
from aoai_api_simulator.record_replay.models import RecordedResponse, get_request_hash, hash_body, hash_request_parts
from aoai_api_simulator.record_replay.openai import forward_to_azure_openai
from aoai_api_simulator.record_replay.persistence import YamlRecordingPersister

logger = logging.getLogger(__name__)

text_content_types = ["application/json", "application/text"]


def get_default_forwarders() -> (
    list[
        Callable[
            [RequestContext],
            fastapi.Response
            | Awaitable[fastapi.Response]
            | requests.Response
            | Awaitable[requests.Response]
            | dict
            | Awaitable[dict]
            | None,
        ]
    ]
):
    # Return a list of functions to call when recording and no matching saved request is found
    #
    # If the function returns a Response object (from FastAPI or requests package)
    # it will be used as the response for the request
    #
    # If the function returns a dict then it should have a "response" property
    # with the response and a "persist" property that is True/False to indicate whether to persist the response
    #
    # If the function returns None, the next function in the list will be called
    return [
        forward_to_azure_openai,
    ]


class ForwardedResponse:
    def __init__(self, response: fastapi.Response, persist_response: bool):
        self._response = response
        self._persist_response = persist_response

    @property
    def response(self) -> fastapi.Response:
        return self._response

    @property
    def persist_response(self) -> bool:
        return self._persist_response


class RecordReplayHandler:
    _recordings: dict[str, dict[int, RecordedResponse]]
    _forwarders: list[
        Callable[
            [RequestContext],
            fastapi.Response
            | Awaitable[fastapi.Response]
            | requests.Response
            | Awaitable[requests.Response]
            | dict
            | Awaitable[dict]
            | None,
        ]
    ]

    def __init__(
        self,
        simulator_mode: str,
        persister: YamlRecordingPersister,
        forwarders: list[
            Callable[
                [RequestContext],
                fastapi.Response
                | Awaitable[fastapi.Response]
                | requests.Response
                | Awaitable[requests.Response]
                | dict
                | Awaitable[dict]
                | None,
            ]
        ],
        autosave: bool,
    ):
        self._simulator_mode = simulator_mode
        self._persister = persister
        self._forwarders = forwarders
        self._autosave = autosave

        # recordings keyed by URL, within a recording, requests are keyed by hash of request values
        self._recordings = {}

    async def _get_recording_for_url(self, url: str) -> dict[int, RecordedResponse] | None:
        recording = self._recordings.get(url)
        if recording:
            return recording

        expect_recording_file = self._simulator_mode == "replay"
        recording = self._persister.load_recording_for_url(url, expect_recording_file)
        if not recording:
            return None

        self._recordings[url] = recording
        return recording

    async def handle_request(self, context: RequestContext) -> fastapi.Response | None:
        request = context.request
        url = request.url.path
        recording = await self._get_recording_for_url(url)
        request_hash = await get_request_hash(request)

        if recording:
            # request_hash = await get_request_hash(request)
            response_info = recording.get(request_hash)
            if response_info:
                headers = {k: v[0] for k, v in response_info.headers.items()}
                for key, value in response_info.context_values.items():
                    context.values[key] = value
                context.values[constants.TARGET_DURATION_MS] = response_info.duration_ms
                return fastapi.Response(
                    content=response_info.body, status_code=response_info.status_code, headers=headers
                )
            logger.debug("No recorded response found for request %s %s", request.method, url)
        else:
            logger.debug("No recording found for URL: %s", url)

        if self._simulator_mode == "record":
            return await self._record_request(context)

        return None

    async def _record_request(self, context: RequestContext) -> fastapi.Response:
        request = context.request

        # Forward the response and capture the request duration
        start_time = time.time()
        forwarded_response: ForwardedResponse | None = await self.forward_request(context)
        end_time = time.time()
        if not forwarded_response:
            raise ValueError(
                "Failed to forward request - no configured forwarders returned a response for"
                + f"{request.method} {request.url}"
            )
        elapsed_time = end_time - start_time
        elapsed_time_ms = int(elapsed_time * 1000)

        recorded_response = await self.get_recorded_response(context, forwarded_response, elapsed_time_ms)
        if forwarded_response.persist_response:
            self.store_recorded_response(request, recorded_response)

        context.values[constants.TARGET_DURATION_MS] = elapsed_time_ms
        return fastapi.Response(
            content=recorded_response.body,
            status_code=recorded_response.status_code,
            headers=forwarded_response.response.headers,  # use original headers in returned content
        )

    async def get_recorded_response(
        self, context: RequestContext, forwarded_response: ForwardedResponse, elapsed_time_ms: int
    ):
        response = forwarded_response.response
        request = context.request
        request_body = await request.body()
        body = response.body
        # limit the request headers we persist - avoid persisting secrets and keep recording size low
        allowed_request_headers = ["content-type", "accept"]
        request_headers = {k: [v] for k, v in request.headers.items() if k.lower() in allowed_request_headers}
        if "content-length" in response.headers:
            del response.headers["content-length"]

        response_content_type = response.headers.get("content-type", "").split(";")[0]
        if response_content_type in text_content_types:
            # simplify format for editing recording files
            body = body.decode("utf-8")

        request_content_type = request.headers.get("content-type", "").split(";")[0]
        if request_content_type in text_content_types:
            request_body = request_body.decode("utf-8")

        request_body_hash = hash_body(request_headers, request_body)
        recorded_response = RecordedResponse(
            status_code=response.status_code,
            headers={k: [v] for k, v in dict(response.headers).items()},
            body=body,
            request_hash=hash_request_parts(
                request.method, request.url.path, request.headers, body_hash=request_body_hash
            ),
            context_values=context.values,
            full_request={
                "method": request.method,
                "uri": str(request.url),
                "headers": request_headers,
                "body": request_body,
            },
            duration_ms=elapsed_time_ms,
        )

        return recorded_response

    def store_recorded_response(self, request: fastapi.Request, recorded_response: RecordedResponse):
        logger.info("📝 Storing recording for %s %s", request.method, request.url)
        recording = self._recordings.get(request.url.path)
        if not recording:
            recording = {}
            self._recordings[request.url.path] = recording
        recording[recorded_response.request_hash] = recorded_response

        if self._autosave:
            # Save the recording to disk
            self._persister.save_recording(request.url.path, recording)

    def save_recordings(self):
        for url, recording in self._recordings.items():
            self._persister.save_recording(url, recording)

    async def forward_request(self, context: RequestContext) -> ForwardedResponse:
        for forwarder in self._forwarders:
            response = forwarder(context)
            if response is not None and inspect.isawaitable(response):
                response = await response
            if response is not None:
                persist_response = True
                # unwrap dictionary response
                if isinstance(response, dict):
                    original_response = response
                    response = original_response["response"]
                    persist_response = original_response.get("persist", persist_response)

                # normalize response to FastAPI Response
                if isinstance(response, fastapi.Response):
                    # Already a FastAPI response
                    pass
                elif isinstance(response, requests.Response):
                    # convert requests response to FastAPI response
                    response = fastapi.Response(
                        content=response.text, status_code=response.status_code, headers=response.headers
                    )
                else:
                    raise ValueError(f"Unhandled response type from forwarder: {type(response)}")

                if "Content-Length" in response.headers.keys():
                    # Content-Length will automatically be set when we return
                    # Strip out before recording to avoid issues
                    del response.headers["Content-Length"]

                # wrap and return
                return ForwardedResponse(response=response, persist_response=persist_response)

        return None
