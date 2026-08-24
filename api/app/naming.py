import re
from datetime import date
from pathlib import Path

NOISE_WORDS = {"transcript", "transcription", "recording", "zoom", "meeting"}


def _strip_leading_compact_date(value: str) -> str:
    return re.sub(r"^\d{6}[\s_-]+", "", value)


def canonical_name(meeting_title: str | None, original_filename: str, meeting_date: date | None) -> str:
    base = meeting_title.strip() if meeting_title and meeting_title.strip() else Path(original_filename).stem
    base = _strip_leading_compact_date(base)
    base = base.lower()
    base = re.sub(r"[^a-z0-9]+", "-", base)
    words = [word for word in base.split("-") if word and word not in NOISE_WORDS]
    slug = "-".join(words) or "meeting-video"
    if meeting_date:
        prefix = meeting_date.isoformat()
        if not slug.startswith(prefix):
            slug = f"{prefix}-{slug}"
    return slug.strip("-")
