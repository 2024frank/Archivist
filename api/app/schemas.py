from datetime import date, datetime

from typing import Literal

from pydantic import BaseModel


class VideoUploadResponse(BaseModel):
    videoId: str
    canonicalName: str
    displayName: str
    status: str


class VideoListItem(BaseModel):
    videoId: str
    canonicalName: str
    displayName: str
    originalFilename: str
    meetingDate: date | None
    source: str | None
    uploadedBy: str | None
    status: str
    createdAt: datetime | None


class FrameResponse(BaseModel):
    videoId: str
    timestamp: str
    timestampMs: int
    frameId: str
    frameUrl: str
    cached: bool


class VideoStatusUpdate(BaseModel):
    status: Literal["completed"]


class VideoStatusResponse(BaseModel):
    videoId: str
    status: str
    videoDeleted: bool
    bytesFreed: int
    framesRetained: int
    completedAt: datetime | None
