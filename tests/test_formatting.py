import pytest

from formatting import format_bytes, format_duration


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0 B"),
        (1023, "1023 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (5 * 1024**2, "5.0 MB"),
        (int(1.9 * 1024**3), "1.9 GB"),
        (2048 * 1024**4, "2048.0 TB"),  # stays in TB instead of running out of units
    ],
)
def test_format_bytes(size, expected):
    assert format_bytes(size) == expected


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0m"),
        (59, "0m"),
        (60, "1m"),
        (5 * 3600 + 12 * 60, "5h 12m"),
        (86400, "1d 0h 0m"),
        (3 * 86400 + 2 * 3600 + 5 * 60, "3d 2h 5m"),
    ],
)
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected
