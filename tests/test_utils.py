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
