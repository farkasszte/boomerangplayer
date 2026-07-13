import pytest
from mixins.cache_mixin import CacheMixin

class DummyPlayer(CacheMixin):
    def __init__(self):
        self.config = {}
        self.cache_window_half = 50
        self.total_frames = 1000
        self.isForward = True

def test_calculate_prefetch_bounds_divisor_1():
    player = DummyPlayer()
    player.config['prefetch_chunk_idx'] = 0  # divisor = 1
    start, end, chunk = player._calculate_prefetch_bounds(500)
    assert chunk == 100
    assert start == 450
    assert end == 550

def test_calculate_prefetch_bounds_forward():
    player = DummyPlayer()
    player.config['prefetch_chunk_idx'] = 1  # divisor = 2
    start, end, chunk = player._calculate_prefetch_bounds(500)
    assert chunk == 50
    assert start == 493
    assert end == 543

def test_calculate_prefetch_bounds_backward():
    player = DummyPlayer()
    player.config['prefetch_chunk_idx'] = 1  # divisor = 2
    player.isForward = False
    start, end, chunk = player._calculate_prefetch_bounds(500)
    assert chunk == 50
    assert start == 457
    assert end == 507
