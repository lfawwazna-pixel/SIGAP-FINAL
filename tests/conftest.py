from datetime import datetime, timedelta, timezone

import pytest


class ManualClock:
    def __init__(self):
        self.elapsed = 0.0
        self.wall_offset = 0.0

    def monotonic(self):
        return 1000.0 + self.elapsed

    def utcnow(self):
        return datetime(2026, 10, 3, tzinfo=timezone.utc) + timedelta(seconds=self.elapsed + self.wall_offset)

    def advance(self, seconds):
        self.elapsed += seconds


@pytest.fixture
def clock():
    return ManualClock()
