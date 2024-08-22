from dataclasses import dataclass
from fastapi import Request


@dataclass
class RecordedResponse:
    request_hash: int
    status_code: int
    headers: dict[str, list[str]]
    body: str
    duration_ms: int
    context_values: dict[str, any]
    # full_request currently here for compatibility with VCR serialization format
    # it _is_ handy for human inspection to have the URL/body etc. in the recording
    full_request: dict


def hash_request_parts(method: str, url: str, body: bytes):
    # Potential future optimisation would be to look for incremental hashing function in Python
    body_hash = hash(body)
    return hash(method + "|" + url + "|" + str(body_hash))


async def get_request_hash(request: Request):
    body = await request.body()
    return hash_request_parts(request.method, request.url.path, body)
