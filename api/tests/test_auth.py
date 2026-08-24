import pytest

from app.auth import require_api_token
from app.config import get_settings


def test_require_api_token_accepts_matching_bearer(monkeypatch):
    monkeypatch.setenv("ARCHIVIST_API_TOKEN", "secret")
    get_settings.cache_clear()
    require_api_token("Bearer secret")


@pytest.mark.parametrize("header", [None, "", "secret", "Bearer wrong"])
def test_require_api_token_rejects_missing_or_wrong_token(monkeypatch, header):
    monkeypatch.setenv("ARCHIVIST_API_TOKEN", "secret")
    get_settings.cache_clear()
    with pytest.raises(Exception):
        require_api_token(header)
