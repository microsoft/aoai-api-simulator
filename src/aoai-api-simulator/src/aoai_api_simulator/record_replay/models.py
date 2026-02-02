import hashlib
import json
import re
from dataclasses import dataclass

from fastapi import Request


@dataclass
# pylint: disable=too-many-instance-attributes
class RecordedResponse:
    request_hash: int
    status_code: int
    headers: dict[str, list[str]]
    body: str | None
    duration_ms: int
    context_values: dict[str, any]
    # full_request currently here for compatibility with VCR serialization format
    # it _is_ handy for human inspection to have the URL/body etc. in the recording
    full_request: dict


import logging
import os
_logger = logging.getLogger(__name__)
_body_counter = 0

def normalize_body_for_hash(body: bytes) -> bytes:
    """Remove dynamic fields from JSON body before hashing."""
    try:
        data = json.loads(body)
        if isinstance(data, dict) and "messages" in data:
            for msg in data["messages"]:
                # Remove all dynamic metadata fields
                for field in ["id", "key", "collection"]:
                    if field in msg:
                        msg[field] = "NORMALIZED"
                # Remove tool_call_id from tool results
                if msg.get("role") == "tool" and "tool_call_id" in msg:
                    msg["tool_call_id"] = "NORMALIZED"
                # Remove tool call IDs from assistant messages
                if msg.get("role") == "assistant" and "tool_calls" in msg:
                    for tc in msg.get("tool_calls", []):
                        if "id" in tc:
                            tc["id"] = "NORMALIZED"
        return json.dumps(data, sort_keys=True).encode("utf-8")
    except (json.JSONDecodeError, TypeError):
        return body


def hash_body(headers: dict, body: bytes) -> int:
    if isinstance(body, str):
        body = body.encode("utf-8")

    content_type = headers.get("content-type", None)
    if content_type:
        if isinstance(content_type, list):
            content_type = content_type[0]

        # If the content is multipart/form-data we need to get the boundary value
        # Since the boundary value changes between requests, if interferes
        # with the hash lookups
        # Once we have the boundary value we can standardise the body content
        # for hashing by replacing the boundary value with a fixed string
        if content_type.startswith("multipart/form-data"):
            boundary_index = content_type.find("boundary=")
            if boundary_index < 0:
                raise ValueError("multipart/form-data content type without boundary")
            boundary = ("--" + content_type[boundary_index + len("boundary=") :]).encode("utf-8")
            static_boundary = b"--AOAI-API-SIMULATOR-BOUNDARY"

            if body[: len(boundary)] == boundary:
                body = static_boundary + body[len(boundary) :]
            body = body.replace(b"\n" + boundary, b"\n" + static_boundary)

        # Normalize JSON bodies to ignore dynamic tool_call_id
        if content_type.startswith("application/json"):
            body = normalize_body_for_hash(body)

    return hashlib.md5(body).hexdigest()


def hash_request_parts(
    method: str, url: str, headers: dict, body: bytes | None = None, body_hash: str | None = None
) -> int:
    # Potential future optimisation would be to look for incremental hashing function in Python
    if body_hash is None:
        if body is None:
            raise ValueError("must specify one of body or body_hash")
        body_hash = hash_body(headers, body)

    result = hashlib.md5((method + "|" + url + "|" + body_hash).encode("utf-8")).hexdigest()
    return result


async def get_request_hash(request: Request):
    body = await request.body()
    return hash_request_parts(request.method, request.url.path, request.headers, body=body)
