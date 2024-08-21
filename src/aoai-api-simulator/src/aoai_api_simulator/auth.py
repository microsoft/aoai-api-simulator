import logging
import secrets
from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


def validate_api_key_header(request: Request, header_name: str, allowed_key_value: str):
    """
    A helper method for validating API Key in the header of a request
    """
    request_api_key = request.headers.get(header_name)
    if request_api_key and secrets.compare_digest(request_api_key, allowed_key_value):
        return True

    logger.warning("🔒 Missing or incorrect API Key provided")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or incorrect API Key",
    )
