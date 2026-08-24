from datetime import date

from app.naming import canonical_name


def test_canonical_name_uses_title_and_date():
    assert canonical_name("CH_Des Archivist", "ignored.mp4", date(2026, 8, 21)) == "2026-08-21-ch-des-archivist"


def test_canonical_name_falls_back_to_filename():
    assert canonical_name(None, "260821 CH_Des Archivist Recording.mp4", date(2026, 8, 21)) == "2026-08-21-ch-des-archivist"


def test_canonical_name_removes_noise_words():
    assert canonical_name(None, "Archivist transcription zoom meeting.mp4", None) == "archivist"
