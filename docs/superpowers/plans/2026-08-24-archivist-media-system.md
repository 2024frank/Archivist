# Archivist Media System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v1 Archivist media backend that accepts MP4 uploads and returns clickable frame URLs for requested timestamps.

**Architecture:** A Dockerized FastAPI service stores MP4s and extracted JPG frames on disk, stores metadata in Postgres, and runs `ffmpeg` synchronously on the first frame request. Caddy will later route `/archivist/api/*` to this service on the DigitalOcean VM without disturbing the existing ChirpStack/Fieldline stack.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2, psycopg, pytest, ffmpeg, Docker Compose, PostgreSQL 16.

**Spec:** `docs/stage-1-planning-signoff.md` and `docs/stage-2-architecture-signoff.md`

## Global Constraints

- MP4-only video uploads in v1.
- Frame endpoint returns JSON containing a clickable `frameUrl`.
- API route prefix is `/archivist/api`.
- Public frame files are served by the API at `/archivist/api/media/frames/{videoId}/{frameFile}`.
- Upload endpoint uses `Authorization: Bearer <ARCHIVIST_API_TOKEN>`.
- Postgres stores metadata only; raw MP4 and JPG files stay on disk.
- Storage root comes from `ARCHIVIST_STORAGE_ROOT`.
- Max upload size comes from `ARCHIVIST_MAX_UPLOAD_MB`.
- Secrets stay in `.env`; `.env` must not be committed.
- Docker services must use log rotation: `max-size=10m`, `max-file=3`.

---

## File Structure

Create:

```text
api/
  Dockerfile
  requirements.txt
  app/
    __init__.py
    main.py
    config.py
    auth.py
    database.py
    models.py
    schemas.py
    storage.py
    media.py
    naming.py
    timestamps.py
    errors.py
  tests/
    conftest.py
    test_timestamps.py
    test_naming.py
    test_auth.py
    test_storage.py
    test_api.py
docker-compose.yml
.env.example
docs/stage-3-implementation-signoff.md
```

Modify:

```text
.gitignore
docs/README.md
```

---

### Task 1: Project Scaffold And Configuration

**Files:**
- Create: `api/requirements.txt`
- Create: `api/app/__init__.py`
- Create: `api/app/config.py`
- Create: `.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `Settings` class in `api.app.config`
- Produces: `get_settings() -> Settings`
- Consumes: environment variables defined in `.env.example`

- [ ] **Step 1: Create dependency manifest**

Create `api/requirements.txt`:

```text
fastapi==0.116.1
uvicorn[standard]==0.35.0
python-multipart==0.0.20
sqlalchemy==2.0.43
psycopg[binary]==3.2.9
pydantic-settings==2.10.1
pytest==8.4.1
httpx==0.28.1
python-ulid==3.1.0
```

- [ ] **Step 2: Create config module**

Create `api/app/config.py`:

```python
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_token: str = Field(alias="ARCHIVIST_API_TOKEN")
    public_base_url: str = Field(alias="ARCHIVIST_PUBLIC_BASE_URL")
    storage_root: Path = Field(alias="ARCHIVIST_STORAGE_ROOT")
    max_upload_mb: int = Field(alias="ARCHIVIST_MAX_UPLOAD_MB")
    database_url: str = Field(alias="ARCHIVIST_DATABASE_URL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3: Add package marker**

Create `api/app/__init__.py`:

```python
"""Archivist media API package."""
```

- [ ] **Step 4: Create `.env.example`**

Create `.env.example`:

```text
ARCHIVIST_API_TOKEN=dev-only-token-change-before-deploy
ARCHIVIST_PUBLIC_BASE_URL=https://206-189-199-110.sslip.io/archivist
ARCHIVIST_STORAGE_ROOT=/opt/archivist/storage
ARCHIVIST_MAX_UPLOAD_MB=2048
ARCHIVIST_DB_NAME=archivist
ARCHIVIST_DB_USER=archivist
ARCHIVIST_DB_PASSWORD=dev-only-password-change-before-deploy
ARCHIVIST_DATABASE_URL=postgresql+psycopg://archivist:dev-only-password-change-before-deploy@archivist-postgres:5432/archivist
```

- [ ] **Step 5: Verify `.gitignore` includes secrets**

Ensure `.gitignore` contains:

```text
.env
.env.*
!.env.example
```

- [ ] **Step 6: Run configuration import check**

Run:

```bash
python3 -m py_compile api/app/config.py
```

Expected: command exits with status `0`.

---

### Task 2: Timestamp Parser

**Files:**
- Create: `api/app/timestamps.py`
- Create: `api/tests/test_timestamps.py`

**Interfaces:**
- Produces: `parse_timestamp(value: str) -> int`
- Produces: `format_timestamp(timestamp_ms: int) -> str`

- [ ] **Step 1: Write tests**

Create `api/tests/test_timestamps.py`:

```python
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
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
cd api && pytest tests/test_timestamps.py -q
```

Expected: fails because `app.timestamps` does not exist yet.

- [ ] **Step 3: Implement timestamp parser**

Create `api/app/timestamps.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd api && pytest tests/test_timestamps.py -q
```

Expected: all tests pass.

---

### Task 3: Canonical Naming

**Files:**
- Create: `api/app/naming.py`
- Create: `api/tests/test_naming.py`

**Interfaces:**
- Produces: `canonical_name(meeting_title: str | None, original_filename: str, meeting_date: date | None) -> str`

- [ ] **Step 1: Write tests**

Create `api/tests/test_naming.py`:

```python
from datetime import date

from app.naming import canonical_name


def test_canonical_name_uses_title_and_date():
    assert canonical_name("CH_Des Archivist", "ignored.mp4", date(2026, 8, 21)) == "2026-08-21-ch-des-archivist"


def test_canonical_name_falls_back_to_filename():
    assert canonical_name(None, "260821 CH_Des Archivist Recording.mp4", date(2026, 8, 21)) == "2026-08-21-ch-des-archivist"


def test_canonical_name_removes_noise_words():
    assert canonical_name(None, "Archivist transcription zoom meeting.mp4", None) == "archivist"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
cd api && pytest tests/test_naming.py -q
```

Expected: fails because `app.naming` does not exist yet.

- [ ] **Step 3: Implement naming module**

Create `api/app/naming.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd api && pytest tests/test_naming.py -q
```

Expected: all tests pass.

---

### Task 4: Database Models And Session

**Files:**
- Create: `api/app/database.py`
- Create: `api/app/models.py`

**Interfaces:**
- Produces: `engine`
- Produces: `SessionLocal`
- Produces: `Base`
- Produces: `init_db() -> None`
- Produces ORM models: `Video`, `VideoFrame`, `ProcessingJob`

- [ ] **Step 1: Implement database module**

Create `api/app/database.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 2: Implement ORM models**

Create `api/app/models.py`:

```python
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String, index=True)
    display_name: Mapped[str] = mapped_column(String)
    original_filename: Mapped[str] = mapped_column(String)
    meeting_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_path: Mapped[str] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    frames: Mapped[list["VideoFrame"]] = relationship(back_populates="video", cascade="all, delete-orphan")

    __table_args__ = (CheckConstraint("status IN ('uploading', 'ready', 'failed')", name="videos_status_check"),)


class VideoFrame(Base):
    __tablename__ = "video_frames"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    timestamp_ms: Mapped[int] = mapped_column(Integer)
    image_path: Mapped[str] = mapped_column(Text)
    public_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    video: Mapped[Video] = relationship(back_populates="frames")

    __table_args__ = (
        CheckConstraint("timestamp_ms >= 0", name="video_frames_timestamp_ms_check"),
        UniqueConstraint("video_id", "timestamp_ms", name="video_frames_video_id_timestamp_ms_key"),
    )


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_type: Mapped[str] = mapped_column(String)
    video_id: Mapped[str | None] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name="processing_jobs_status_check"),)
```

- [ ] **Step 3: Compile modules**

Run:

```bash
python3 -m py_compile api/app/database.py api/app/models.py
```

Expected: command exits with status `0`.

---

### Task 5: Authentication And Error Helpers

**Files:**
- Create: `api/app/auth.py`
- Create: `api/app/errors.py`
- Create: `api/tests/test_auth.py`

**Interfaces:**
- Produces: `require_api_token(authorization: str | None) -> None`
- Produces: `api_error(status_code: int, code: str, message: str) -> HTTPException`

- [ ] **Step 1: Write auth tests**

Create `api/tests/test_auth.py`:

```python
import pytest

from app.auth import require_api_token


def test_require_api_token_accepts_matching_bearer(monkeypatch):
    monkeypatch.setenv("ARCHIVIST_API_TOKEN", "secret")
    require_api_token("Bearer secret")


@pytest.mark.parametrize("header", [None, "", "secret", "Bearer wrong"])
def test_require_api_token_rejects_missing_or_wrong_token(monkeypatch, header):
    monkeypatch.setenv("ARCHIVIST_API_TOKEN", "secret")
    with pytest.raises(Exception):
        require_api_token(header)
```

- [ ] **Step 2: Implement error helper**

Create `api/app/errors.py`:

```python
from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": code, "message": message})
```

- [ ] **Step 3: Implement auth helper**

Create `api/app/auth.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd api && pytest tests/test_auth.py -q
```

Expected: all tests pass.

---

### Task 6: Storage And ffmpeg Media Functions

**Files:**
- Create: `api/app/storage.py`
- Create: `api/app/media.py`
- Create: `api/tests/test_storage.py`

**Interfaces:**
- Produces: `video_dir(video_id: str) -> Path`
- Produces: `frame_dir(video_id: str) -> Path`
- Produces: `frame_filename(timestamp_ms: int) -> str`
- Produces: `frame_public_url(video_id: str, timestamp_ms: int) -> str`
- Produces: `extract_frame(input_path: Path, output_path: Path, timestamp_ms: int) -> None`

- [ ] **Step 1: Write storage tests**

Create `api/tests/test_storage.py`:

```python
from pathlib import Path

from app.storage import frame_filename


def test_frame_filename_pads_milliseconds():
    assert frame_filename(503000) == "000503000.jpg"
    assert frame_filename(0) == "000000000.jpg"
```

- [ ] **Step 2: Implement storage helpers**

Create `api/app/storage.py`:

```python
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
```

- [ ] **Step 3: Implement ffmpeg extraction**

Create `api/app/media.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd api && pytest tests/test_storage.py -q
```

Expected: all tests pass.

---

### Task 7: FastAPI Application And Endpoints

**Files:**
- Create: `api/app/schemas.py`
- Create: `api/app/main.py`
- Create: `api/tests/conftest.py`
- Create: `api/tests/test_api.py`

**Interfaces:**
- Produces: FastAPI app named `app`
- Produces endpoints:
  - `GET /health`
  - `POST /videos`
  - `GET /videos/{video_id}/frame`
  - `GET /media/frames/{video_id}/{frame_file}`

- [ ] **Step 1: Create schemas**

Create `api/app/schemas.py`:

```python
from pydantic import BaseModel


class VideoUploadResponse(BaseModel):
    videoId: str
    canonicalName: str
    displayName: str
    status: str


class FrameResponse(BaseModel):
    videoId: str
    timestamp: str
    timestampMs: int
    frameId: str
    frameUrl: str
    cached: bool
```

- [ ] **Step 2: Implement FastAPI app**

Create `api/app/main.py` with:

```python
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from ulid import ULID

from app.auth import require_api_token
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.errors import api_error
from app.media import extract_frame
from app.models import Video, VideoFrame
from app.naming import canonical_name
from app.schemas import FrameResponse, VideoUploadResponse
from app.storage import frame_dir, frame_filename, frame_public_url, video_dir
from app.timestamps import format_timestamp, parse_timestamp

app = FastAPI(title="Archivist Media API")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"ok": True, "service": "archivist-api"}


@app.post("/videos", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    meetingTitle: str | None = Form(None),
    meetingDate: date | None = Form(None),
    source: str | None = Form(None),
    uploadedBy: str | None = Form(None),
    authorization: str | None = Header(None),
):
    require_api_token(authorization)
    if not file.filename or not file.filename.lower().endswith(".mp4"):
        raise api_error(415, "unsupported_file_type", "Only .mp4 uploads are supported.")

    video_id = f"vid_{ULID()}"
    display_name = meetingTitle.strip() if meetingTitle and meetingTitle.strip() else Path(file.filename).stem
    slug = canonical_name(meetingTitle, file.filename, meetingDate)
    path = video_dir(video_id) / "original.mp4"
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    written = 0

    with path.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > max_bytes:
                path.unlink(missing_ok=True)
                raise api_error(413, "upload_too_large", "Upload exceeds configured size limit.")
            out.write(chunk)

    with SessionLocal() as db:
        video = Video(
            id=video_id,
            canonical_name=slug,
            display_name=display_name,
            original_filename=file.filename,
            meeting_date=meetingDate,
            source=source,
            uploaded_by=uploadedBy,
            storage_path=str(path),
            status="ready",
        )
        db.add(video)
        db.commit()

    return VideoUploadResponse(videoId=video_id, canonicalName=slug, displayName=display_name, status="ready")


@app.get("/videos/{video_id}/frame", response_model=FrameResponse)
def get_frame(video_id: str, timestamp: str):
    try:
        timestamp_ms = parse_timestamp(timestamp)
    except ValueError:
        raise api_error(400, "invalid_timestamp", "Timestamp must be seconds, MM:SS, or HH:MM:SS.")

    with SessionLocal() as db:
        video = db.get(Video, video_id)
        if not video:
            raise api_error(404, "video_not_found", "Video was not found.")
        if video.status != "ready":
            raise api_error(409, "video_not_ready", "Video is not ready for frame extraction.")

        existing = db.query(VideoFrame).filter_by(video_id=video_id, timestamp_ms=timestamp_ms).one_or_none()
        if existing:
            return FrameResponse(
                videoId=video_id,
                timestamp=format_timestamp(timestamp_ms),
                timestampMs=timestamp_ms,
                frameId=existing.id,
                frameUrl=existing.public_url,
                cached=True,
            )

        image_path = frame_dir(video_id) / frame_filename(timestamp_ms)
        try:
            extract_frame(Path(video.storage_path), image_path, timestamp_ms)
        except Exception:
            raise api_error(500, "frame_extraction_failed", "Could not extract frame from video.")

        frame = VideoFrame(
            id=f"frame_{ULID()}",
            video_id=video_id,
            timestamp_ms=timestamp_ms,
            image_path=str(image_path),
            public_url=frame_public_url(video_id, timestamp_ms),
        )
        db.add(frame)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            frame = db.query(VideoFrame).filter_by(video_id=video_id, timestamp_ms=timestamp_ms).one()

        return FrameResponse(
            videoId=video_id,
            timestamp=format_timestamp(timestamp_ms),
            timestampMs=timestamp_ms,
            frameId=frame.id,
            frameUrl=frame.public_url,
            cached=False,
        )


@app.get("/media/frames/{video_id}/{frame_file}")
def open_frame(video_id: str, frame_file: str):
    path = frame_dir(video_id) / frame_file
    resolved = path.resolve()
    root = frame_dir(video_id).resolve()
    if root not in resolved.parents or not resolved.exists():
        raise api_error(404, "frame_not_found", "Frame was not found.")
    return FileResponse(resolved, media_type="image/jpeg")
```

- [ ] **Step 3: Add API tests**

Create focused tests in `api/tests/test_api.py` for:

```python
from app.main import health


def test_health_response():
    assert health() == {"ok": True, "service": "archivist-api"}
```

- [ ] **Step 4: Run available tests**

Run:

```bash
cd api && pytest -q
```

Expected: all tests pass.

---

### Task 8: Docker Compose And Container Build

**Files:**
- Create: `api/Dockerfile`
- Create: `docker-compose.yml`

**Interfaces:**
- Produces Docker services:
  - `archivist-api`
  - `archivist-postgres`

- [ ] **Step 1: Create API Dockerfile**

Create `api/Dockerfile`:

```dockerfile
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create compose file**

Create `docker-compose.yml`:

```yaml
services:
  archivist-postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${ARCHIVIST_DB_NAME}
      POSTGRES_USER: ${ARCHIVIST_DB_USER}
      POSTGRES_PASSWORD: ${ARCHIVIST_DB_PASSWORD}
    volumes:
      - archivist-postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${ARCHIVIST_DB_USER} -d ${ARCHIVIST_DB_NAME}"]
      interval: 10s
      timeout: 5s
      retries: 5
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  archivist-api:
    build: ./api
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "127.0.0.1:8010:8000"
    volumes:
      - ${ARCHIVIST_STORAGE_ROOT}:${ARCHIVIST_STORAGE_ROOT}
    depends_on:
      archivist-postgres:
        condition: service_healthy
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  archivist-postgres-data:
```

- [ ] **Step 3: Validate compose**

Run:

```bash
docker compose config --quiet
```

Expected: command exits with status `0`.

- [ ] **Step 4: Build images**

Run:

```bash
docker compose build
```

Expected: image builds successfully.

---

### Task 9: Stage 3 Implementation Sign-Off Document

**Files:**
- Create: `docs/stage-3-implementation-signoff.md`
- Modify: `docs/README.md`

**Interfaces:**
- Produces implementation checklist used before testing sign-off.

- [ ] **Step 1: Create implementation sign-off doc**

Create `docs/stage-3-implementation-signoff.md`:

````markdown
# Archivist Meeting Media System: Stage 3 Implementation Sign-Off

## Status

```text
Stage: Implementation
Owner: Kwaku Kusi Appiah
Review state: Pending sign-off
Last updated: 2026-08-24
Depends on: docs/superpowers/plans/2026-08-24-archivist-media-system.md
```

## Checklist

```text
[ ] Project scaffold created
[ ] Config loading implemented
[ ] Timestamp parser implemented
[ ] Canonical naming implemented
[ ] Database models implemented
[ ] API token auth implemented
[ ] Storage helpers implemented
[ ] ffmpeg frame extraction implemented
[ ] FastAPI endpoints implemented
[ ] Dockerfile implemented
[ ] Docker Compose implemented
[ ] Local tests pass
[ ] Docker build passes
[ ] Kwaku signs off Stage 3 Implementation
```

## Sign-Off

```text
Implementation approved by:
Date:
Notes:
```
````

- [ ] **Step 2: Update docs index**

Add `stage-3-implementation-signoff.md` to `docs/README.md`.

---

### Task 10: Local Verification Gate

**Files:**
- No new files.

**Interfaces:**
- Consumes all earlier tasks.
- Produces verified local implementation ready for VM deployment planning.

- [ ] **Step 1: Run Python unit tests**

Run:

```bash
cd api && pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run compile check**

Run:

```bash
python3 -m py_compile api/app/*.py
```

Expected: command exits with status `0`.

- [ ] **Step 3: Validate compose**

Run:

```bash
docker compose config --quiet
```

Expected: command exits with status `0`.

- [ ] **Step 4: Build containers**

Run:

```bash
docker compose build
```

Expected: build succeeds.

- [ ] **Step 5: Confirm secret safety**

Run:

```bash
git status --short --ignored
```

Expected:

```text
.env appears ignored or absent from tracked changes.
No secret-bearing files are staged.
```

---

## Self-Review

Spec coverage:

```text
MP4 uploads: Task 7
Clickable frame URLs: Tasks 6 and 7
Stable IDs: Task 7
Canonical names: Task 3
Timestamp parsing: Task 2
Postgres metadata: Task 4
Disk storage: Task 6
ffmpeg extraction: Task 6
Docker Compose: Task 8
Testing gate: Task 10
Stage sign-off: Task 9
```

Placeholder scan:

```text
No unresolved placeholder markers are intentionally left in task instructions.
```

Type consistency:

```text
The plan consistently uses parse_timestamp, format_timestamp, canonical_name,
frame_filename, frame_public_url, extract_frame, Video, VideoFrame, and SessionLocal.
```

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-24-archivist-media-system.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.
