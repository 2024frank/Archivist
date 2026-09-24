import shutil
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


def delete_video_file(video_id: str) -> int:
    """Delete the stored source video for a video id and return bytes freed."""
    path = storage_root() / "videos" / video_id
    if not path.exists():
        return 0
    freed = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    shutil.rmtree(path, ignore_errors=True)
    return freed
