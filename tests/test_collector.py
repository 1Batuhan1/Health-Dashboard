from collections import namedtuple
from types import SimpleNamespace

import psutil

import collector

Partition = namedtuple("Partition", "device mountpoint fstype opts")
Usage = namedtuple("Usage", "total used free percent")
Temp = namedtuple("Temp", "label current high critical")


# --- Real system (smoke tests) ---------------------------------------------

def test_snapshot_has_every_section():
    data = collector.snapshot()
    assert set(data) == {"time", "uptime", "cpu", "memory", "disks", "temps", "processes"}
    assert data["uptime"] > 0


def test_snapshot_values_are_in_range():
    collector.snapshot()  # the first cpu_percent measurement is always 0
    data = collector.snapshot()
    assert 0 <= data["cpu"]["total"] <= 100
    assert len(data["cpu"]["per_core"]) == collector.CPU_COUNT
    assert 0 < data["memory"]["used"] <= data["memory"]["total"]
    assert all(0 <= d["percent"] <= 100 for d in data["disks"])


def test_processes_include_this_test_run():
    processes = collector.processes()
    assert any(p["pid"] == psutil.Process().pid for p in processes)
    expected_keys = {"pid", "name", "username", "cpu_percent", "memory_percent", "rss",
                     "threads", "status", "cmdline", "create_time"}
    assert all(set(p) == expected_keys for p in processes)


# --- Fake data (exact behavior) ----------------------------------------------

def test_cpu_total_is_the_average_of_all_cores(monkeypatch):
    monkeypatch.setattr(psutil, "cpu_percent", lambda percpu=False: [10.0, 30.0])
    assert collector.cpu()["total"] == 20.0


def test_disks_skip_pseudo_filesystems_and_unreadable_drives(monkeypatch):
    partitions = [
        Partition("/dev/sda1", "/", "ext4", "rw"),
        Partition("tmpfs", "/run", "tmpfs", "rw"),
        Partition("/dev/loop0", "/snap/core", "squashfs", "ro"),
        Partition("/dev/sr0", "/media/cdrom", "iso9660", "ro"),
    ]

    def disk_usage(mountpoint):
        if mountpoint == "/media/cdrom":
            raise OSError("drive not ready")
        return Usage(100, 25, 75, 25.0)

    monkeypatch.setattr(psutil, "disk_partitions", lambda: partitions)
    monkeypatch.setattr(psutil, "disk_usage", disk_usage)

    disks = collector.disks()
    assert [d["mount"] for d in disks] == ["/"]
    assert disks[0] == {"mount": "/", "fstype": "ext4", "total": 100, "used": 25, "percent": 25.0}


def test_temperatures_empty_when_unsupported(monkeypatch):
    monkeypatch.delattr(psutil, "sensors_temperatures", raising=False)
    assert collector.temperatures() == []


def test_temperatures_fill_in_missing_labels_and_limits(monkeypatch):
    chips = {"coretemp": [Temp("Core 0", 45.0, 80.0, 100.0), Temp("", 50.0, None, 95.0)]}
    monkeypatch.setattr(psutil, "sensors_temperatures", lambda: chips, raising=False)

    temps = collector.temperatures()
    assert temps[0] == {"chip": "coretemp", "label": "Core 0", "current": 45.0, "high": 80.0}
    assert temps[1]["label"] == "coretemp"  # an empty label falls back to the chip name
    assert temps[1]["high"] == 95.0  # no "high" value falls back to "critical"


def test_processes_normalize_cpu_and_fill_missing_values(monkeypatch):
    def fake_process(**info):
        defaults = {"pid": 1, "name": "init", "username": "root", "cpu_percent": 0.0,
                    "memory_percent": 0.0, "memory_info": SimpleNamespace(rss=1024),
                    "num_threads": 1, "status": "sleeping", "cmdline": ["/sbin/init"], "create_time": 1.0}
        return SimpleNamespace(info={**defaults, **info})

    fakes = [
        fake_process(pid=0, name="System Idle Process"),  # skipped
        fake_process(pid=42, cpu_percent=200.0, cmdline=["python", "main.py"]),
        fake_process(pid=43, name=None, username=None, cpu_percent=None, memory_info=None,
                     num_threads=None, status=None, cmdline=None),  # access denied everywhere
    ]
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: iter(fakes))
    monkeypatch.setattr(collector, "CPU_COUNT", 4)

    busy, denied = collector.processes()
    assert busy["pid"] == 42
    assert busy["cpu_percent"] == 50.0  # 200% of one core on a 4-core machine
    assert busy["cmdline"] == "python main.py"
    assert busy["rss"] == 1024
    assert denied == {
        "pid": 43, "name": "?", "username": "-", "cpu_percent": 0.0, "memory_percent": 0.0,
        "rss": 0, "threads": 0, "status": "-", "cmdline": "", "create_time": 1.0,
    }
