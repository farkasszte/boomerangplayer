import pytest
from utils import format_time, format_chrono_time

def test_format_time():
    assert format_time(None) == "0:00"
    assert format_time(0) == "0:00"
    assert format_time(500) == "0:00"
    assert format_time(1000) == "0:01"
    assert format_time(61000) == "1:01"
    assert format_time(3661000) == "1:01:01"

def test_format_chrono_time():
    assert format_chrono_time(None) == "00:00.000"
    assert format_chrono_time(0) == "00:00.000"
    assert format_chrono_time(500) == "00:00.500"
    assert format_chrono_time(61234) == "01:01.234"

def test_get_embedded_video_offset(tmp_path):
    from utils import get_embedded_video_offset
    
    # Non-jpeg file should return None
    txt_file = tmp_path / "test.txt"
    txt_file.write_bytes(b"hello world")
    assert get_embedded_video_offset(str(txt_file)) is None

    # JPEG without MP4
    plain_jpg = tmp_path / "plain.jpg"
    plain_jpg.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9")
    assert get_embedded_video_offset(str(plain_jpg)) is None

    # Motion photo: JPEG followed by MP4 ftyp box (size=32 -> 0x00000020)
    motion_jpg = tmp_path / "motion.jpg"
    jpeg_part = b"\xff\xd8\xff\xe0" + b"\x00" * 50 + b"\xff\xd9"
    mp4_box = (32).to_bytes(4, 'big') + b"ftypisom" + b"\x00" * 20
    motion_jpg.write_bytes(jpeg_part + mp4_box)
    
    offset = get_embedded_video_offset(str(motion_jpg))
    assert offset == len(jpeg_part)
