from pathlib import Path

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app, health
from app.models import Video
from app.storage import frame_filename, video_dir


def test_health_response():
    assert health() == {"ok": True, "service": "archivist-api"}


def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_upload_requires_bearer_token():
    reset_database()
    with TestClient(app) as client:
        response = client.post(
            "/videos",
            files={"file": ("meeting.mp4", b"fake", "video/mp4")},
        )
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "unauthorized"


def test_upload_rejects_non_mp4():
    reset_database()
    with TestClient(app) as client:
        response = client.post(
            "/videos",
            headers={"Authorization": "Bearer test-token"},
            files={"file": ("meeting.mov", b"fake", "video/quicktime")},
        )
    assert response.status_code == 415
    assert response.json()["detail"]["error"] == "unsupported_file_type"


def test_upload_mp4_creates_video_record():
    reset_database()
    with TestClient(app) as client:
        response = client.post(
            "/videos",
            headers={"Authorization": "Bearer test-token"},
            data={"meetingTitle": "CH_Des Archivist", "meetingDate": "2026-08-21", "source": "manual"},
            files={"file": ("260821 CH_Des Archivist.mp4", b"fake mp4 bytes", "video/mp4")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["videoId"].startswith("vid_")
    assert body["canonicalName"] == "2026-08-21-ch-des-archivist"
    assert body["status"] == "ready"

    with SessionLocal() as db:
        video = db.get(Video, body["videoId"])
        assert video is not None
        assert Path(video.storage_path).exists()


def test_frame_request_extracts_then_uses_cache(monkeypatch):
    reset_database()
    calls = []

    def fake_extract_frame(input_path, output_path, timestamp_ms):
        calls.append((input_path, output_path, timestamp_ms))
        output_path.write_bytes(b"\xff\xd8\xff\xd9")

    monkeypatch.setattr("app.main.extract_frame", fake_extract_frame)

    video_id = "vid_01M0TNASGK82R2QRCP1V1SS1EG"
    with SessionLocal() as db:
        video_path = video_dir(video_id) / "original.mp4"
        video_path.write_bytes(b"fake")
        db.add(
            Video(
                id=video_id,
                canonical_name="2026-08-21-ch-des-archivist",
                display_name="CH_Des Archivist",
                original_filename="meeting.mp4",
                storage_path=str(video_path),
                status="ready",
            )
        )
        db.commit()

    with TestClient(app) as client:
        headers = {"Authorization": "Bearer test-token"}
        first = client.get(f"/videos/{video_id}/frame", headers=headers, params={"timestamp": "8:23"})
        second = client.get(f"/videos/{video_id}/frame", headers=headers, params={"timestamp": "00:08:23"})
        media = client.get(f"/media/frames/{video_id}/{frame_filename(503000)}")

    assert first.status_code == 200
    assert first.json()["cached"] is False
    assert first.json()["frameUrl"].endswith(f"/api/media/frames/{video_id}/000503000.jpg")
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert len(calls) == 1
    assert media.status_code == 200
    assert media.headers["content-type"] == "image/jpeg"


def test_frame_request_requires_bearer_token():
    reset_database()
    with TestClient(app) as client:
        response = client.get("/videos/vid_01M0TNASGK82R2QRCP1V1SS1EG/frame", params={"timestamp": "8:23"})

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "unauthorized"
