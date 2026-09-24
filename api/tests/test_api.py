from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app, health
from app.models import Video
from app.storage import frame_filename, storage_root, video_dir


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


def test_list_videos_returns_video_metadata():
    reset_database()
    with SessionLocal() as db:
        db.add(
            Video(
                id="vid_01M0TNASGK82R2QRCP1V1SS1EG",
                canonical_name="2026-08-21-ch-des-archivist",
                display_name="CH_Des Archivist",
                original_filename="260821 CH_Des Archivist - video.mp4",
                meeting_date=date(2026, 8, 21),
                source="downloaded-video",
                uploaded_by="Kwaku",
                storage_path="/tmp/original.mp4",
                status="ready",
            )
        )
        db.commit()

    with TestClient(app) as client:
        response = client.get("/videos")

    assert response.status_code == 200
    assert response.json() == [
        {
            "videoId": "vid_01M0TNASGK82R2QRCP1V1SS1EG",
            "canonicalName": "2026-08-21-ch-des-archivist",
            "displayName": "CH_Des Archivist",
            "originalFilename": "260821 CH_Des Archivist - video.mp4",
            "meetingDate": "2026-08-21",
            "source": "downloaded-video",
            "uploadedBy": "Kwaku",
            "status": "ready",
            "createdAt": response.json()[0]["createdAt"],
        }
    ]


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


def seed_ready_video(video_id: str, payload: bytes = b"fake-video-bytes") -> Path:
    video_path = video_dir(video_id) / "original.mp4"
    video_path.write_bytes(payload)
    with SessionLocal() as db:
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
    return video_path


def test_complete_video_deletes_source_and_keeps_metadata():
    reset_database()
    video_id = "vid_01M0TNASGK82R2QRCP1V1SS1CMP"
    payload = b"x" * 2048
    video_path = seed_ready_video(video_id, payload)

    with TestClient(app) as client:
        response = client.put(
            f"/videos/{video_id}/status",
            headers={"Authorization": "Bearer test-token"},
            json={"status": "completed"},
        )
        listed = client.get("/videos")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "completed"
    assert body["videoDeleted"] is True
    assert body["bytesFreed"] == len(payload)
    assert body["completedAt"] is not None
    assert not video_path.exists()
    assert not (storage_root() / "videos" / video_id).exists()
    assert [item["videoId"] for item in listed.json()] == [video_id]
    assert listed.json()[0]["status"] == "completed"


def test_complete_video_is_idempotent():
    reset_database()
    video_id = "vid_01M0TNASGK82R2QRCP1V1SS1IDE"
    seed_ready_video(video_id)

    with TestClient(app) as client:
        headers = {"Authorization": "Bearer test-token"}
        first = client.put(f"/videos/{video_id}/status", headers=headers, json={"status": "completed"})
        second = client.put(f"/videos/{video_id}/status", headers=headers, json={"status": "completed"})

    assert first.json()["videoDeleted"] is True
    assert second.status_code == 200
    assert second.json()["videoDeleted"] is False
    assert second.json()["bytesFreed"] == 0
    assert second.json()["status"] == "completed"


def test_completed_video_rejects_new_frame_requests():
    reset_database()
    video_id = "vid_01M0TNASGK82R2QRCP1V1SS1GON"
    seed_ready_video(video_id)

    with TestClient(app) as client:
        headers = {"Authorization": "Bearer test-token"}
        client.put(f"/videos/{video_id}/status", headers=headers, json={"status": "completed"})
        frame = client.get(f"/videos/{video_id}/frame", headers=headers, params={"timestamp": "00:01:00"})

    assert frame.status_code == 410
    assert frame.json()["detail"]["error"] == "video_completed"


def test_complete_video_requires_bearer_token():
    reset_database()
    with TestClient(app) as client:
        response = client.put(
            "/videos/vid_01M0TNASGK82R2QRCP1V1SS1EG/status",
            json={"status": "completed"},
        )

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "unauthorized"


def test_complete_unknown_video_returns_404():
    reset_database()
    with TestClient(app) as client:
        response = client.put(
            "/videos/vid_does_not_exist/status",
            headers={"Authorization": "Bearer test-token"},
            json={"status": "completed"},
        )

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "video_not_found"


def test_complete_rejects_unsupported_status_value():
    reset_database()
    video_id = "vid_01M0TNASGK82R2QRCP1V1SS1BAD"
    seed_ready_video(video_id)

    with TestClient(app) as client:
        response = client.put(
            f"/videos/{video_id}/status",
            headers={"Authorization": "Bearer test-token"},
            json={"status": "archived"},
        )

    assert response.status_code == 422
