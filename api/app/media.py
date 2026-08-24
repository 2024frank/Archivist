import os
import subprocess
from pathlib import Path

from app.timestamps import format_timestamp


def extract_frame(input_path: Path, output_path: Path, timestamp_ms: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".tmp.jpg")
    if tmp_path.exists():
        tmp_path.unlink()
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        format_timestamp(timestamp_ms),
        "-i",
        str(input_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(tmp_path),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=60, capture_output=True, text=True)
        os.replace(tmp_path, output_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
