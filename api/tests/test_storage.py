from app.storage import frame_filename


def test_frame_filename_pads_milliseconds():
    assert frame_filename(503000) == "000503000.jpg"
    assert frame_filename(0) == "000000000.jpg"
