import secrets

from app.config import get_settings
from app.errors import api_error


def require_api_token(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise api_error(401, "unauthorized", "Missing bearer token.")
    supplied = authorization.removeprefix("Bearer ").strip()
    expected = get_settings().api_token
    if not secrets.compare_digest(supplied, expected):
        raise api_error(401, "unauthorized", "Invalid bearer token.")
