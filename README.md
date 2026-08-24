# Archivist Media API

Archivist is a small FastAPI service for storing meeting videos and returning clickable frame-image URLs for requested timestamps.

The first production deployment is running on the DigitalOcean VM at:

```text
https://206-189-199-110.sslip.io/archivist
```

## What It Does

- Accepts MP4 meeting-video uploads from an AI automation or operator.
- Stores original videos on the VM filesystem.
- Stores video and frame metadata in Postgres.
- Extracts JPEG frames with `ffmpeg` when given a `videoId` and timestamp.
- Returns a public/clickable frame URL.
- Keeps upload and frame-generation endpoints protected with a bearer token.

## API

```text
GET  /archivist/api/health
GET  /archivist/api/videos
POST /archivist/api/videos
GET  /archivist/api/videos/{videoId}/frame?timestamp=HH:MM:SS
GET  /archivist/api/media/frames/{videoId}/{timestampMs}.jpg
```

## Find A Video ID

Before requesting a frame, list the uploaded videos and choose the matching `videoId` from the metadata:

```bash
curl "https://206-189-199-110.sslip.io/archivist/api/videos?limit=50"
```

Each item includes:

```text
videoId
canonicalName
displayName
originalFilename
meetingDate
source
uploadedBy
status
createdAt
```

## Upload Example

```bash
curl -H "Authorization: Bearer $ARCHIVIST_API_TOKEN" \
  -F "meetingTitle=CH_Des Archivist" \
  -F "meetingDate=2026-08-21" \
  -F "source=box-download" \
  -F "uploadedBy=Kwaku" \
  -F "file=@meeting.mp4;type=video/mp4" \
  https://206-189-199-110.sslip.io/archivist/api/videos
```

## Frame Example

```bash
curl -H "Authorization: Bearer $ARCHIVIST_API_TOKEN" \
  "https://206-189-199-110.sslip.io/archivist/api/videos/{videoId}/frame?timestamp=00:28:35"
```

The response includes `frameUrl`, which can be opened directly in a browser.

## Local Development

Create `.env` from `.env.example`, then run:

```bash
docker compose up -d --build
```

Run tests:

```bash
cd api
python -m pytest -q
```

## Deployment Notes

The deployed VM copy lives at:

```text
/opt/archivist
```

The service joins the existing `chirpstack_default` Docker network so the existing Caddy container can proxy:

```text
/archivist/api/* -> archivist-api:8000
```

Real secrets belong only in `.env`; `.env` is intentionally ignored by Git.

## Engineering Docs

See `docs/` for the planning, architecture, implementation, and deployment sign-off records.
