# Archivist Meeting Media System: Stage 4 Deployment Sign-Off

## Status

```text
Stage: Deployment
Owner: Kwaku Kusi Appiah
Review state: Completed
Last updated: 2026-08-24
Deployment host: root@206.189.199.110
Public base URL: https://206-189-199-110.sslip.io/archivist
```

## Checklist

```text
[x] Application copied to /opt/archivist on the VM
[x] Real .env installed on the VM with restricted permissions
[x] Persistent storage directories created under /opt/archivist/storage
[x] Postgres 16 container started for Archivist metadata
[x] FastAPI container built and started
[x] Archivist API joined the existing chirpstack_default Docker network
[x] Existing Caddyfile backed up before changes
[x] Caddy route added for /archivist/api/*
[x] Caddy configuration validated
[x] Caddy reloaded without replacing the existing Fieldline/ChirpStack routes
[x] Public health endpoint verified
[x] Unauthorized frame request verified as rejected
[x] MP4 upload verified through the public endpoint
[x] Frame extraction verified through the public endpoint
[x] Returned frame URL verified as a clickable JPEG URL
```

## Verified Endpoints

```text
GET  /archivist/api/health
GET  /archivist/api/videos
POST /archivist/api/videos
GET  /archivist/api/videos/{videoId}/frame?timestamp=HH:MM:SS
GET  /archivist/api/media/frames/{videoId}/{timestampMs}.jpg
```

## Smoke Test Evidence

```text
Upload HTTP status: 200
Frame request HTTP status: 200
Frame image HTTP status: 200
Frame image type: JPEG image data, 320x180
Smoke-test video id: vid_01M0TNPBK35AFBS593YYFH432E
Smoke-test frame URL: https://206-189-199-110.sslip.io/archivist/api/media/frames/vid_01M0TNPBK35AFBS593YYFH432E/000001000.jpg
```

## Sign-Off

```text
Deployment completed by: Codex
Date: 2026-08-24
Notes: Deployed under /archivist/api/* to avoid conflict with the existing /api/* Fieldline route.
```
