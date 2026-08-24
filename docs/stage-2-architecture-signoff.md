# Archivist Meeting Media System: Stage 2 Architecture Sign-Off

## Status

```text
Stage: Architecture
Owner: Kwaku Kusi Appiah
Review state: Approved
Last updated: 2026-08-24
Depends on: stage-1-planning-signoff.md
```

## Architecture Summary

The Archivist media system will be a small Dockerized backend deployed beside the existing ChirpStack/Fieldline stack on the DigitalOcean VM.

It will expose a dedicated API namespace:

```text
/archivist/api/*
```

It will store video and frame metadata in Postgres, store MP4 and JPG files on disk under the Archivist storage root, and use `ffmpeg` inside the API container to extract frames on demand.

For v1, frame extraction is synchronous on the first request and cached afterward. Repeated requests return the existing frame URL without running `ffmpeg` again.

## System Components

```text
AI Automation
  Uploads MP4 files and calls frame endpoint.

Caddy
  Routes /archivist/api/* to the Archivist API.

Archivist API
  FastAPI service.
  Authenticates uploads.
  Creates video records.
  Validates MP4 uploads.
  Parses timestamps.
  Runs ffmpeg for frame extraction.
  Returns JSON responses with clickable frame URLs.

Archivist Postgres
  Stores metadata only.
  Does not store binary video or frame blobs.

Archivist Storage
  Stores uploaded MP4s and extracted JPG frames.
  Root path from ARCHIVIST_STORAGE_ROOT.
```

## Deployment Topology

Current VM:

```text
Host: 206.189.199.110
Public hostname: 206-189-199-110.sslip.io
Existing stack path: /opt/chirpstack
New stack path: /opt/archivist
Storage root: /opt/archivist/storage
```

Recommended VM layout:

```text
/opt/archivist/
  docker-compose.yml
  .env
  api/
    Dockerfile
    app/
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
  storage/
    videos/
    frames/
```

The repository folder on Kwaku's machine is:

```text
/Users/kwaku/Desktop/Archivist
```

The local `.env` file is not committed. Deployment will copy or recreate the required environment variables on the VM.

## Runtime Services

### archivist-api

Responsibilities:

- Serve `/health`.
- Serve `POST /videos`.
- Serve `GET /videos/{video_id}/frame`.
- Serve or coordinate static frame URLs.
- Validate authentication for mutating endpoints.
- Talk to Postgres.
- Read and write media files.
- Run `ffmpeg`.

Technology:

```text
Python 3.12
FastAPI
Uvicorn
SQLAlchemy or SQLModel
psycopg
python-multipart
python-ulid or equivalent ULID library
ffmpeg installed in container
```

### archivist-postgres

Responsibilities:

- Store video and frame metadata.
- Store processing/job metadata.
- Enforce uniqueness constraints.

Technology:

```text
PostgreSQL 16
Docker volume or bind-mounted DB data directory
```

### Caddy

The existing Caddy container currently lives in the ChirpStack Compose project and owns ports 80 and 443.

Recommended v1 routing choice:

```text
Add routes to the existing /opt/chirpstack/Caddyfile.
Do not run a second public Caddy on ports 80/443.
```

Target route:

```caddy
handle_path /archivist/api/* {
    reverse_proxy archivist-api:8000
}
```

Implementation note:

The existing Caddy container must be able to reach `archivist-api`. For v1, Caddy does not need direct access to frame files because the API serves frame files through `/archivist/api/media/...`.

Recommended v1 routing strategy:

```text
API serves frame files through /archivist/api/media/...
Caddy only reverse-proxies /archivist/api/* to the API.
```

This avoids cross-compose static-file mounts. It is slightly less efficient than direct Caddy file serving but simpler and safer for the first version.

## API Contract

### Health Check

```http
GET /archivist/api/health
```

Response:

```json
{
  "ok": true,
  "service": "archivist-api"
}
```

### Upload Video

```http
POST /archivist/api/videos
Authorization: Bearer <ARCHIVIST_API_TOKEN>
Content-Type: multipart/form-data
```

Form fields:

```text
file: required MP4 file
meetingTitle: optional string
meetingDate: optional YYYY-MM-DD
source: optional string
uploadedBy: optional string
```

Validation:

```text
Reject if Authorization token is missing or wrong.
Reject if file is missing.
Reject if file extension is not .mp4.
Reject if content type is clearly not video/mp4 or application/octet-stream.
Reject if upload exceeds ARCHIVIST_MAX_UPLOAD_MB.
Reject if meetingDate is present but invalid.
```

Success response:

```json
{
  "videoId": "vid_01K3A8M9Z6N2Q7P4R5T6V8X9YB",
  "canonicalName": "2026-08-21-ch-des-archivist",
  "displayName": "CH_Des Archivist",
  "status": "ready"
}
```

### Get Frame URL

```http
GET /archivist/api/videos/{videoId}/frame?timestamp=00:08:23
```

Behavior:

```text
1. Look up video by videoId.
2. Parse timestamp to timestampMs.
3. Check if frame already exists in video_frames.
4. If cached, return existing frameUrl.
5. If not cached, run ffmpeg against the MP4.
6. Store JPG under frames/{videoId}/{timestampMs}.jpg.
7. Insert video_frames record.
8. Return frameUrl.
```

Success response:

```json
{
  "videoId": "vid_01K3A8M9Z6N2Q7P4R5T6V8X9YB",
  "timestamp": "00:08:23.000",
  "timestampMs": 503000,
  "frameId": "frame_01K3A8Q2H3BK9T8V6E1M4P7R2C",
  "frameUrl": "https://206-189-199-110.sslip.io/archivist/api/media/frames/vid_01K3A8M9Z6N2Q7P4R5T6V8X9YB/000503000.jpg",
  "cached": false
}
```

### Open Frame URL

```http
GET /archivist/api/media/frames/{videoId}/{frameFile}
```

Behavior:

```text
Return image/jpeg if the file exists and belongs to a known frame record.
Return 404 otherwise.
```

The media endpoint does not require authentication in v1 because frame URLs are intended to be clickable by collaborators. The URL is unguessable because it contains the ULID-style video ID and timestamp-derived frame filename.

## Error Contract

All JSON API errors use:

```json
{
  "error": "machine_readable_code",
  "message": "Human-readable explanation."
}
```

Required errors:

```text
401 unauthorized
400 invalid_timestamp
400 invalid_meeting_date
400 missing_file
413 upload_too_large
415 unsupported_file_type
404 video_not_found
404 frame_not_found
409 video_not_ready
500 frame_extraction_failed
500 database_error
```

## Database Schema

### videos

```sql
CREATE TABLE videos (
  id TEXT PRIMARY KEY,
  canonical_name TEXT NOT NULL,
  display_name TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  meeting_date DATE,
  source TEXT,
  uploaded_by TEXT,
  storage_path TEXT NOT NULL,
  duration_ms INTEGER,
  status TEXT NOT NULL CHECK (status IN ('uploading', 'ready', 'failed')),
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX videos_canonical_name_idx ON videos (canonical_name);
CREATE INDEX videos_meeting_date_idx ON videos (meeting_date);
CREATE INDEX videos_status_idx ON videos (status);
```

### video_frames

```sql
CREATE TABLE video_frames (
  id TEXT PRIMARY KEY,
  video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  timestamp_ms INTEGER NOT NULL CHECK (timestamp_ms >= 0),
  image_path TEXT NOT NULL,
  public_url TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (video_id, timestamp_ms)
);

CREATE INDEX video_frames_video_id_idx ON video_frames (video_id);
```

### processing_jobs

```sql
CREATE TABLE processing_jobs (
  id TEXT PRIMARY KEY,
  job_type TEXT NOT NULL,
  video_id TEXT REFERENCES videos(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
);

CREATE INDEX processing_jobs_video_id_idx ON processing_jobs (video_id);
CREATE INDEX processing_jobs_status_idx ON processing_jobs (status);
```

## Storage Layout

Storage root:

```text
ARCHIVIST_STORAGE_ROOT=/opt/archivist/storage
```

Directory structure:

```text
/opt/archivist/storage/
  videos/
    vid_01K3A8M9Z6N2Q7P4R5T6V8X9YB/
      original.mp4
  frames/
    vid_01K3A8M9Z6N2Q7P4R5T6V8X9YB/
      000503000.jpg
```

Frame filename:

```text
{timestampMs padded to 9 digits}.jpg
```

Examples:

```text
000000000.jpg
000503000.jpg
003600000.jpg
```

## Naming Rules

Input sources:

```text
meetingTitle
originalFilename
meetingDate
```

Canonical name algorithm:

```text
1. Prefer meetingTitle if provided.
2. Otherwise use originalFilename without extension.
3. Remove common suffixes: transcript, transcription, recording, zoom, meeting.
4. Lowercase.
5. Replace spaces, underscores, and repeated punctuation with hyphens.
6. Strip leading and trailing hyphens.
7. Prefix with meetingDate if available and not already present.
8. If collision exists, append -2, -3, etc.
```

Example:

```text
meetingDate: 2026-08-21
originalFilename: 260821 CH_Des Archivist.mp4
canonicalName: 2026-08-21-ch-des-archivist
```

## Timestamp Parser

Accepted:

```text
seconds: 503
minutes:seconds: 8:23
hours:minutes:seconds: 00:08:23
fractional seconds: 00:08:23.500
```

Rejected:

```text
negative values
empty values
non-numeric units
minute/second segments >= 60
```

Output:

```text
integer timestampMs
canonical timestamp string HH:MM:SS.mmm
```

## ffmpeg Behavior

Command pattern:

```bash
ffmpeg -hide_banner -loglevel error -ss <timestamp> -i <input.mp4> -frames:v 1 -q:v 2 <output.jpg>
```

Rules:

```text
Use timeout to prevent stuck processes.
Write to a temporary file first.
Atomically rename temp file to final JPG path.
If extraction fails, delete temp file.
Record failure in processing_jobs or error log.
```

## Environment Variables

Required:

```text
ARCHIVIST_API_TOKEN
ARCHIVIST_PUBLIC_BASE_URL
ARCHIVIST_STORAGE_ROOT
ARCHIVIST_MAX_UPLOAD_MB
ARCHIVIST_DB_NAME
ARCHIVIST_DB_USER
ARCHIVIST_DB_PASSWORD
ARCHIVIST_DATABASE_URL
```

Example non-secret values:

```text
ARCHIVIST_PUBLIC_BASE_URL=https://206-189-199-110.sslip.io/archivist
ARCHIVIST_STORAGE_ROOT=/opt/archivist/storage
ARCHIVIST_MAX_UPLOAD_MB=2048
ARCHIVIST_DB_NAME=archivist
ARCHIVIST_DB_USER=archivist
```

Secrets must stay in `.env` and must not be committed.

## Docker Compose Requirements

Services:

```text
archivist-api
archivist-postgres
```

Required settings:

```text
restart: unless-stopped
log rotation: max-size 10m, max-file 3
Postgres healthcheck
API depends on healthy Postgres
storage bind mount
.env loaded by compose
```

The API container must include:

```text
ffmpeg
Python dependencies
application code
```

## Security Architecture

V1 security posture:

```text
Upload endpoint requires API token.
Health endpoint may be public.
Frame URLs are public but unguessable.
Raw MP4 paths are never exposed.
Directory traversal is blocked by resolving paths under storage root.
Only .mp4 uploads are accepted.
Upload size is capped.
Docker logs are rotated.
Secrets are excluded from Git.
```

Future security upgrades:

```text
Signed frame URLs.
Separate automation tokens.
Per-meeting access control.
Audit log for uploads and frame requests.
DigitalOcean Spaces private bucket with signed object URLs.
```

## Testing Architecture

Unit tests:

```text
timestamp parser
canonical name generator
auth token validation
storage path resolver
API schema validation
```

Integration tests:

```text
upload MP4 creates video row and file
invalid upload returns 415
frame request creates JPG and DB row
second frame request uses cache
frame URL opens image/jpeg
missing video returns 404
bad timestamp returns 400
```

Deployment tests:

```text
docker compose config validates
services start
/archivist/api/health returns ok
test MP4 upload works on VM
frame URL opens from browser
disk usage remains stable
Docker log rotation is active
existing ChirpStack/Fieldline routes still respond
```

## Deployment Sequence

```text
1. Build and test locally.
2. Confirm .env exists locally and is not committed.
3. Copy application files to /opt/archivist on VM.
4. Create /opt/archivist/.env on VM.
5. Create /opt/archivist/storage.
6. Start archivist-postgres and archivist-api.
7. Add Caddy route for /archivist/api/*.
8. Reload or recreate Caddy safely.
9. Verify /archivist/api/health.
10. Upload test MP4.
11. Request frame URL.
12. Open frame URL.
13. Check disk usage and logs.
14. Record deployment sign-off.
```

## Rollback Plan

If deployment breaks:

```text
1. Remove or comment Archivist route from Caddyfile.
2. Reload Caddy.
3. Stop Archivist containers.
4. Keep storage and DB volume intact for inspection.
5. Confirm existing Fieldline/ChirpStack routes still work.
```

No rollback step should delete uploaded MP4s, frames, or database data unless explicitly approved.

## Architecture Checklist

```text
[x] API service design documented
[x] Database schema documented
[x] File storage layout documented
[x] Frame extraction flow documented
[x] Route prefix documented
[x] Error responses documented
[x] Security assumptions documented
[x] Testing strategy documented
[x] Deployment sequence documented
[x] Kwaku signs off Stage 2 Architecture
```

## Sign-Off

```text
Architecture approved by: Kwaku Kusi Appiah
Date: 2026-08-24
Notes: Approved via "let's go" after reviewing the Stage 2 architecture gate.
```

## Next Stage After Approval

After Stage 2 is signed off, move to Stage 3: Implementation Plan.

Stage 3 will produce a task-by-task implementation plan covering:

- Project scaffolding.
- FastAPI app setup.
- Database migrations.
- Upload endpoint.
- Timestamp parser.
- Frame extraction.
- Media URL serving.
- Tests.
- Docker Compose.
- VM deployment.
