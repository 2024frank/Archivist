from decimal import Decimal, InvalidOperation


def parse_timestamp(value: str) -> int:
    raw = value.strip()
    if not raw:
        raise ValueError("timestamp is required")

    parts = raw.split(":")
    if len(parts) > 3:
        raise ValueError("timestamp has too many segments")

    try:
        if len(parts) == 1:
            seconds = Decimal(parts[0])
        elif len(parts) == 2:
            minutes = int(parts[0])
            sec = Decimal(parts[1])
            if minutes < 0 or sec < 0 or sec >= 60:
                raise ValueError("invalid minutes or seconds")
            seconds = Decimal(minutes * 60) + sec
        else:
            hours = int(parts[0])
            minutes = int(parts[1])
            sec = Decimal(parts[2])
            if hours < 0 or minutes < 0 or minutes >= 60 or sec < 0 or sec >= 60:
                raise ValueError("invalid hours, minutes, or seconds")
            seconds = Decimal(hours * 3600 + minutes * 60) + sec
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid timestamp") from exc

    if seconds < 0:
        raise ValueError("timestamp cannot be negative")
    return int(seconds * 1000)


def format_timestamp(timestamp_ms: int) -> str:
    if timestamp_ms < 0:
        raise ValueError("timestamp cannot be negative")
    millis = timestamp_ms % 1000
    total_seconds = timestamp_ms // 1000
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
