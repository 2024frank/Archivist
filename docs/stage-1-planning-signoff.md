# Archivist Meeting Media System: Stage 1 Planning Sign-Off

## Status

```text
Stage: Planning
Owner: Kwaku Kusi Appiah
Review state: Approved
Last updated: 2026-08-24
```

## Purpose

Archivist needs a media service that lets AI automation upload meeting videos and later retrieve a still image from a specific timestamp in a specific video.

The first workflow is:

```text
1. A meeting video is uploaded as an MP4.
2. The system stores metadata and assigns the video a stable ID.
3. Archivist stores that video ID with the meeting/transcript record.
4. When a transcript or AI agent references a timestamp, the system extracts or finds the matching frame.
5. The system returns a clickable image URL.
```

## Product Goal

Build a reliable first version of the Archivist media backend that supports:

- MP4 meeting video uploads.
- Stable video IDs.
- Human-readable normalized video names.
- Timestamp-to-frame extraction.
- Cached frame reuse.
- Clickable frame URLs.
- Postgres metadata storage.
- Local VM or attached-volume media storage for the first version.

## Confirmed Decisions

### Video Upload Format

The system will accept meeting videos as MP4 files.

```text
Decision: MP4-only for v1
Reason: Keeps validation, ffmpeg handling, and automation simple.
```

### Frame Response

The frame endpoint will return a JSON response containing a clickable URL.

Example:

```json
{
  "videoId": "vid_01K3A8M9Z6N2Q7P4R5T6V8X9YB",
  "timestampMs": 503000,
  "frameUrl": "https://206-189-199-110.sslip.io/archivist/api/media/frames/vid_01K3A8M9Z6N2Q7P4R5T6V8X9YB/000503000.jpg"
}
```

```text
Decision: Return URL, not raw image bytes, by default.
Reason: Easier for people, Notion, automation, and docs to open or attach.
```

### API Route Prefix

The existing VM already routes `/api/*` to another service. Archivist will use a separate prefix.

```text
Decision: /archivist/api/*
Reason: Avoids breaking existing Fieldline/ChirpStack services.
```

### Authentication

The upload and administrative endpoints will require an API token.

```text
Decision: Bearer token or X-API-Key style token for v1.
Reason: Simple, automation-friendly, and enough for a private internal service.
```

A local credentials file already exists at:

```text
/Users/kwaku/Desktop/Archivist/.env
```

It contains generated secrets and must not be committed.

### Database

The system will use Postgres for metadata.

Postgres stores:

- Video records.
- Frame records.
- Processing status.
- Storage paths.
- Transcript/media relationships later.

Postgres does not store:

- Raw MP4 files.
- Image blobs.
- Large binary media archives.

### Storage Direction

The current recommendation is to use a VM-attached storage volume for the first version.

```text
Decision: VM volume first, DigitalOcean Spaces later if needed.
Reason: Local MP4 files are simpler for ffmpeg extraction and faster to implement.
```

Preferred media root:

```text
/opt/archivist/storage
```

## System Scope For V1

V1 includes:

- `POST /archivist/api/videos`
- `GET /archivist/api/videos/:videoId/frame?timestamp=...`
- MP4 upload validation.
- Video metadata creation.
- Stable video ID generation.
- Canonical name normalization.
- Timestamp normalization to milliseconds.
- Frame extraction using ffmpeg.
- Frame cache lookup.
- Clickable frame URL response.
- Docker-based deployment.
- Log rotation.
- Basic health endpoint.

V1 does not include:

- A full web UI.
- Video streaming.
- Video editing.
- User accounts.
- Fine-grained permissions.
- Full visual search.
- Automatic scene detection.
- Long-term object storage migration.
- Notion write-back automation.

## Endpoint Contracts

### Upload Video

```http
POST /archivist/api/videos
Authorization: Bearer <ARCHIVIST_API_TOKEN>
Content-Type: multipart/form-data
```

Fields:

```text
file: MP4 video file
meetingTitle: optional human title
meetingDate: optional YYYY-MM-DD date
source: optional source such as box, zoom, manual, automation
uploadedBy: optional uploader identifier
```

Success response:

```json
{
  "videoId": "vid_01K3A8M9Z6N2Q7P4R5T6V8X9YB",
  "canonicalName": "2026-08-21-ch-des-archivist",
  "displayName": "CH_Des Archivist",
  "status": "uploaded"
}
```

### Get Frame URL

```http
GET /archivist/api/videos/:videoId/frame?timestamp=00:08:23
```

Success response:

```json
{
  "videoId": "vid_01K3A8M9Z6N2Q7P4R5T6V8X9YB",
  "timestamp": "00:08:23.000",
  "timestampMs": 503000,
  "frameId": "frame_01K3A8Q2H3BK9T8V6E1M4P7R2C",
  "frameUrl": "https://206-189-199-110.sslip.io/archivist/api/media/frames/vid_01K3A8M9Z6N2Q7P4R5T6V8X9YB/000503000.jpg"
}
```

## ID And Naming Rules

The system must not use filenames as permanent IDs.

Each video has:

```text
videoId: stable machine ID
canonicalName: normalized human-readable slug
displayName: editable human title
originalFilename: exact uploaded filename
```

Example:

```text
videoId: vid_01K3A8M9Z6N2Q7P4R5T6V8X9YB
canonicalName: 2026-08-21-ch-des-archivist
displayName: CH_Des Archivist
originalFilename: 260821 CH_Des Archivist.mp4
```

Preferred ID format:

```text
vid_<ULID>
frame_<ULID>
```

## Timestamp Rules

Accepted timestamp formats:

```text
8:23
00:08:23
08:23.5
503
```

Internal storage format:

```text
timestampMs: integer milliseconds from video start
```

Cache path format:

```text
frames/{videoId}/{timestampMs padded to 9 digits}.jpg
```

Example:

```text
frames/vid_01K3A8M9Z6N2Q7P4R5T6V8X9YB/000503000.jpg
```

## Data Model Draft

### videos

```text
id
canonical_name
display_name
original_filename
meeting_date
source
uploaded_by
storage_path
duration_ms
status
created_at
updated_at
```

### video_frames

```text
id
video_id
timestamp_ms
image_path
public_url
created_at
```

### processing_jobs

```text
id
job_type
video_id
status
error_message
created_at
started_at
finished_at
```

## Testing Expectations

Before deployment sign-off, the system must prove:

- A valid MP4 can be uploaded.
- A non-MP4 is rejected.
- Upload requires the API token.
- Timestamps parse correctly.
- A frame can be extracted from a real video.
- A repeated request returns the cached frame URL.
- The returned frame URL opens in a browser.
- Missing videos return a clear error.
- Invalid timestamps return a clear error.
- Docker logs cannot grow without limit.

## Deployment Expectations

The VM deployment must:

- Not break current ChirpStack/Fieldline services.
- Use `/archivist/api/*`, not `/api/*`.
- Use Docker Compose.
- Use environment variables from `.env`.
- Keep MP4 files and frames under `/opt/archivist/storage` or the attached volume mount.
- Include log rotation from day one.
- Expose a health endpoint.

## Current Infrastructure Notes

Current VM:

```text
Host: 206.189.199.110
OS: Ubuntu 24.04.4 LTS
Current free disk after cleanup: about 17 GB
Existing public route: 206-189-199-110.sslip.io
Existing /api/* route: already used by Fieldline backend
```

An email has been sent to Pratyush requesting more storage or an attached DigitalOcean volume for Archivist media.

## Open Questions

These must be answered before architecture sign-off:

```text
[ ] Should frame URLs be public unguessable URLs or signed expiring URLs?
[ ] What maximum MP4 upload size should v1 allow? Current .env says 2048 MB.
[ ] Should uploaded MP4 files be retained permanently in v1?
[ ] Should frame extraction happen synchronously on request or through a background job?
[ ] Should automation use Authorization: Bearer token or X-API-Key?
[ ] Should the first implementation use Python/FastAPI or Node/Express?
```

Recommended defaults:

```text
Frame URLs: public but unguessable for v1
Max upload: 2048 MB
MP4 retention: retain until manually deleted
Frame extraction: synchronous on first request, cached afterward
Auth style: Authorization: Bearer <token>
Implementation stack: Python/FastAPI because ffmpeg and file handling are straightforward
```

## Stage 1 Checklist

```text
[x] Confirm system purpose
[x] Confirm MP4-only video uploads
[x] Confirm frames return as clickable URLs
[x] Confirm API route prefix: /archivist/api
[x] Confirm auth method: API token
[x] Confirm database: PostgreSQL
[x] Confirm current first-version scope
[x] Confirm what is not included in v1
[x] Confirm storage choice: VM volume first, DigitalOcean Spaces later
[x] Confirm open-question defaults
[x] Kwaku signs off Stage 1 Planning
```

## Sign-Off

```text
Planning approved by: Kwaku Kusi Appiah
Date: 2026-08-24
Notes: Approved via "let's go" after reviewing the Stage 1 defaults.
```

## Next Stage After Approval

After Stage 1 is signed off, move to Stage 2: Architecture Sign-Off.

Stage 2 will define:

- Exact service layout.
- Docker Compose design.
- Caddy routing.
- Database schema SQL.
- Storage paths.
- API error contract.
- Testing strategy.
- Deployment sequence.
