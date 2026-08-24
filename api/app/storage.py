from pathlib import Path

from app.config import get_settings


def storage_root() -> Path:
    root = get_settings().storage_root
    root.mkdir(parents=True, exist_ok=True)
    return root


def video_dir(video_id: str) -> Path:
    path = storage_root() / "videos" / video_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def frame_dir(video_id: str) -> Path:
    path = storage_root() / "frames" / video_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def frame_filename(timestamp_ms: int) -> str:
    return f"{timestamp_ms:09d}.jpg"


def frame_public_url(video_id: str, timestamp_ms: int) -> str:
    base = get_settings().public_base_url.rstrip("/")
    return f"{base}/api/media/frames/{video_id}/{frame_filename(timestamp_ms)}"
