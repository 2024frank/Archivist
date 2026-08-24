from datetime import date
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, Header, Query, UploadFile
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
from app.schemas import FrameResponse, VideoListItem, VideoUploadResponse
from app.storage import frame_dir, frame_filename, frame_public_url, video_dir
from app.timestamps import format_timestamp, parse_timestamp


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Archivist Media API", lifespan=lifespan)


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


@app.get("/videos", response_model=list[VideoListItem])
def list_videos(
    limit: int = Query(50, ge=1, le=200),
):
    with SessionLocal() as db:
        videos = db.query(Video).order_by(Video.created_at.desc(), Video.id.desc()).limit(limit).all()

    return [
        VideoListItem(
            videoId=video.id,
            canonicalName=video.canonical_name,
            displayName=video.display_name,
            originalFilename=video.original_filename,
            meetingDate=video.meeting_date,
            source=video.source,
            uploadedBy=video.uploaded_by,
            status=video.status,
            createdAt=video.created_at,
        )
        for video in videos
    ]


@app.get("/videos/{video_id}/frame", response_model=FrameResponse)
def get_frame(video_id: str, timestamp: str, authorization: str | None = Header(None)):
    require_api_token(authorization)
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
