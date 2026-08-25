# Archivist Media API

Archivist is a deployed API for uploading meeting videos and pulling still images from those videos by timestamp.

The core workflow is:

```text
1. Upload an MP4 video.
2. Get back a generated videoId.
3. Later, call GET /videos to see all uploaded video metadata and identify the right videoId.
4. Request a frame by passing videoId and timestamp to GET /videos/{videoId}/frame.
5. Open the returned frameUrl.
```

Production base URL:

```text
https://206-189-199-110.sslip.io/archivist
```

API base URL:

```text
https://206-189-199-110.sslip.io/archivist/api
```

## What This System Does

- Stores meeting videos uploaded as `.mp4` files.
- Generates a stable `videoId` for each uploaded video.
- Lists uploaded videos with enough metadata to identify the right `videoId`.
- Extracts a JPEG frame from a video at a requested timestamp.
- Returns a clickable `frameUrl` that can be opened in a browser.
- Stores metadata in Postgres.
- Stores original videos and generated frames on the VM filesystem.

## Authentication Rules

```text
Public / no token required:
GET /videos
GET /media/frames/{videoId}/{frameFile}

Bearer token required:
POST /videos
GET /videos/{videoId}/frame
```

`GET /videos` is public because it only returns lookup metadata so users can find the right `videoId`.

Uploading videos and generating frame URLs require:

```text
Authorization: Bearer <ARCHIVIST_API_TOKEN>
```

Use the configured `ARCHIVIST_API_TOKEN` value for the environment where the API is running.

## Endpoints

```text
GET  /health
GET  /videos
POST /videos
GET  /videos/{videoId}/frame?timestamp=HH:MM:SS
GET  /media/frames/{videoId}/{timestampMs}.jpg
```

When using the production deployment, prefix these paths with:

```text
https://206-189-199-110.sslip.io/archivist/api
```

## How Users Normally Use It

Most users should think about the system in three stages:

```text
Upload video -> Find the video record -> Retrieve a frame from that video
```

The important idea is that the timestamp is **not** passed to the image URL endpoint. The timestamp is passed to the protected frame-generation endpoint:

```text
GET /videos/{videoId}/frame?timestamp=00:28:35
```

That endpoint returns a `frameUrl`. The `frameUrl` points to the generated JPEG image:

```text
GET /media/frames/{videoId}/{frameFile}
```

So the two GET endpoints have different jobs:

```text
GET /videos
Shows uploaded video metadata so users can choose the right videoId.

GET /videos/{videoId}/frame?timestamp=...
Creates or finds a frame for a specific video timestamp and returns frameUrl.

GET /media/frames/{videoId}/{frameFile}
Opens an already-created JPEG image. It does not accept timestamp.
```

Typical user flow:

```text
Step 1: Upload an MP4.
Result: API returns videoId, canonicalName, displayName, and status.

Step 2: List uploaded videos.
Result: API returns all recent video metadata, including videoId, title, file name, meeting date, source, uploader, and status.

Step 3: Pick the matching videoId.
Example: choose the video where displayName is "CH_Des Archivist" and meetingDate is "2026-08-21".

Step 4: Request the frame.
Pass videoId in the URL path and timestamp as the query parameter.

Step 5: Open the returned frameUrl.
The frameUrl is a public JPEG link that can be clicked or shared.
```

## 1. Check Health

Use this to confirm the API is online:

```bash
curl "https://206-189-199-110.sslip.io/archivist/api/health"
```

Expected response:

```json
{
  "ok": true,
  "service": "archivist-api"
}
```

## 2. Upload An MP4 Video

Only `.mp4` files are accepted.

```bash
export ARCHIVIST_API_TOKEN="PASTE_TOKEN_HERE"

curl -H "Authorization: Bearer $ARCHIVIST_API_TOKEN" \
  -F "meetingTitle=CH_Des Archivist" \
  -F "meetingDate=2026-08-21" \
  -F "source=box-download" \
  -F "uploadedBy=Kwaku" \
  -F "file=@/path/to/meeting.mp4;type=video/mp4" \
  "https://206-189-199-110.sslip.io/archivist/api/videos"
```

Required form field:

```text
file  MP4 video file
```

Optional form fields:

```text
meetingTitle  Human-readable meeting title
meetingDate   YYYY-MM-DD
source        Where the file came from, such as box-download, zoom, drive, or automation
uploadedBy    Person or automation that uploaded the file
```

Example upload response:

```json
{
  "videoId": "vid_01M0TP1NKCFMAWPAQZ09PKN23S",
  "canonicalName": "2026-08-21-ch-des-archivist",
  "displayName": "CH_Des Archivist",
  "status": "ready"
}
```

Save the `videoId`. If you lose it, call `GET /videos` to find it again.

## 3. Find A Video ID From Metadata

Before requesting a frame, list uploaded videos and choose the matching `videoId`.

```bash
curl "https://206-189-199-110.sslip.io/archivist/api/videos?limit=50"
```

Example response:

```json
[
  {
    "videoId": "vid_01M0TP1NKCFMAWPAQZ09PKN23S",
    "canonicalName": "2026-08-21-ch-des-archivist",
    "displayName": "CH_Des Archivist",
    "originalFilename": "260821 CH_Des Archivist - video.mp4",
    "meetingDate": "2026-08-21",
    "source": "downloaded-video",
    "uploadedBy": "Kwaku",
    "status": "ready",
    "createdAt": "2026-08-24T20:03:00Z"
  }
]
```

Use these fields to match the right video:

```text
videoId           Unique ID used for frame requests
canonicalName     Normalized searchable name
displayName       Human-readable title
originalFilename  Original uploaded file name
meetingDate       Meeting date if supplied
source            Where the video came from
uploadedBy        Person or automation that uploaded it
status            ready, uploading, or failed
createdAt         Upload record creation time
```

`limit` is optional. It defaults to `50` and can be between `1` and `200`.

## 4. Request A Frame URL

After a video is uploaded, request a frame with the `videoId` and timestamp.

```bash
curl -H "Authorization: Bearer $ARCHIVIST_API_TOKEN" \
  "https://206-189-199-110.sslip.io/archivist/api/videos/vid_01M0TP1NKCFMAWPAQZ09PKN23S/frame?timestamp=00:28:35"
```

Accepted timestamp formats:

```text
seconds      95
MM:SS        28:35
HH:MM:SS     00:28:35
fractional   00:28:35.500
```

Example response:

```json
{
  "videoId": "vid_01M0TP1NKCFMAWPAQZ09PKN23S",
  "timestamp": "00:28:35.000",
  "timestampMs": 1715000,
  "frameId": "frame_01M0TP1ZZRVHSRDSADPABMQSZ7",
  "frameUrl": "https://206-189-199-110.sslip.io/archivist/api/media/frames/vid_01M0TP1NKCFMAWPAQZ09PKN23S/001715000.jpg",
  "cached": false
}
```

Open `frameUrl` directly in a browser to see the image.

If the same frame was already extracted, `cached` will be `true` and the API will return the existing URL.

## 5. Open A Frame Image

Frame image URLs are public/clickable:

```text
https://206-189-199-110.sslip.io/archivist/api/media/frames/{videoId}/{timestampMs}.jpg
```

Example:

```text
https://206-189-199-110.sslip.io/archivist/api/media/frames/vid_01M0TP1NKCFMAWPAQZ09PKN23S/001715000.jpg
```

These URLs return JPEG images.

Do not pass timestamps to this endpoint. This endpoint only opens a frame file that already exists. To choose a timestamp, use:

```text
GET /videos/{videoId}/frame?timestamp=00:28:35
```

## Complete Example Workflow

```bash
export ARCHIVIST_API_TOKEN="PASTE_TOKEN_HERE"

# 1. Confirm API is online.
curl "https://206-189-199-110.sslip.io/archivist/api/health"

# 2. Upload a meeting video.
curl -H "Authorization: Bearer $ARCHIVIST_API_TOKEN" \
  -F "meetingTitle=CH_Des Archivist" \
  -F "meetingDate=2026-08-21" \
  -F "source=box-download" \
  -F "uploadedBy=Kwaku" \
  -F "file=@/Users/kwaku/Downloads/260821 CH_Des Archivist - video.mp4;type=video/mp4" \
  "https://206-189-199-110.sslip.io/archivist/api/videos"

# 3. List videos later if you need to recover the videoId.
curl "https://206-189-199-110.sslip.io/archivist/api/videos?limit=50"

# 4. Request a frame from the chosen video.
curl -H "Authorization: Bearer $ARCHIVIST_API_TOKEN" \
  "https://206-189-199-110.sslip.io/archivist/api/videos/vid_01M0TP1NKCFMAWPAQZ09PKN23S/frame?timestamp=00:28:35"

# 5. Open the frameUrl returned by step 4.
```

## Automation Integration

An AI automation should use this flow:

```text
1. POST /videos with the MP4 file and metadata.
2. Store the returned videoId.
3. If the videoId is unknown later, call GET /videos and match by metadata.
4. Call GET /videos/{videoId}/frame?timestamp=... with the bearer token.
5. Use the returned frameUrl anywhere a clickable image link is needed.
```

Recommended upload metadata:

```text
meetingTitle  Clear human name, for example CH_Des Archivist
meetingDate   Meeting date, not upload date
source        box, zoom, drive, manual-upload, or automation name
uploadedBy    Person or automation identity
```

## Current Known Uploaded Video

The first real uploaded meeting video is:

```text
videoId: vid_01M0TP1NKCFMAWPAQZ09PKN23S
displayName: CH_Des Archivist
originalFilename: 260821 CH_Des Archivist - video.mp4
meetingDate: 2026-08-21
status: ready
```

Useful verified frame examples:

```text
00:26:40 -> Meeting Transcripts screen
00:28:35 -> Meetings Log database
00:49:23 -> Release Tracker
00:51:54 -> Dashboard Creator/Editor wiki
```

## Error Codes

Common API errors:

```text
401 unauthorized             Missing or wrong bearer token on protected endpoints
413 upload_too_large         Uploaded MP4 exceeds configured max size
415 unsupported_file_type    File is not an MP4
400 invalid_timestamp        Timestamp is not seconds, MM:SS, or HH:MM:SS
404 video_not_found          videoId does not exist
409 video_not_ready          Video exists but is not ready for extraction
500 frame_extraction_failed  ffmpeg could not extract the requested frame
```

Error responses use this shape:

```json
{
  "detail": {
    "error": "video_not_found",
    "message": "Video was not found."
  }
}
```

## Local Development

Create `.env` from `.env.example`.

```bash
cp .env.example .env
```

Update `.env` with real local values, then run:

```bash
docker compose up -d --build
```

Run tests:

```bash
cd api
python -m pytest -q
```

The local API container listens on:

```text
http://127.0.0.1:8010
```

## Deployment Notes

The deployed VM copy lives at:

```text
/opt/archivist
```

The API runs in Docker Compose with:

```text
archivist-api       FastAPI + ffmpeg
archivist-postgres  Postgres 16 metadata database
```

The existing Caddy container proxies:

```text
/archivist/api/* -> archivist-api:8000
```

Media storage path on the VM:

```text
/opt/archivist/storage
```

Use private deployment configuration for environment-specific credentials.

## Engineering Docs

See `docs/` for planning, architecture, implementation, and deployment sign-off records.

Important files:

```text
docs/stage-1-planning-signoff.md
docs/stage-2-architecture-signoff.md
docs/stage-3-implementation-signoff.md
docs/stage-4-deployment-signoff.md
docs/superpowers/plans/2026-08-24-archivist-media-system.md
```
