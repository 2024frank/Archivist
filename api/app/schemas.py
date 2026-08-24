from datetime import date, datetime

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
