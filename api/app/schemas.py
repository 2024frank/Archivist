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
