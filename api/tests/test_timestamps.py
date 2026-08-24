import pytest

from app.timestamps import format_timestamp, parse_timestamp


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("503", 503000),
        ("8:23", 503000),
        ("00:08:23", 503000),
        ("08:23.500", 503500),
        ("00:08:23.050", 503050),
    ],
)
def test_parse_timestamp_accepts_supported_formats(raw, expected):
    assert parse_timestamp(raw) == expected


@pytest.mark.parametrize("raw", ["", "-1", "abc", "1:60", "1:2:60", "1:2:3:4"])
def test_parse_timestamp_rejects_invalid_formats(raw):
    with pytest.raises(ValueError):
        parse_timestamp(raw)


def test_format_timestamp_returns_canonical_value():
    assert format_timestamp(503050) == "00:08:23.050"
