"""Sistem metriklerini psutil ile toplar.

Bu modülü yalnızca tek bir yerden (CollectorWorker) ve düzenli aralıklarla çağır:
cpu_percent() değerleri iki çağrı arasındaki farktan hesaplanır, başka bir yerden
de çağrılırsa ölçüm aralıkları karışır.
"""
import time

import psutil

CPU_COUNT = psutil.cpu_count() or 1
IGNORED_FSTYPES = {"squashfs", "tmpfs", "devtmpfs", "overlay"}
PROC_ATTRS = ["pid", "name", "username", "cpu_percent", "memory_percent",
              "memory_info", "num_threads", "status", "cmdline", "create_time"]


def _cpu_freq_mhz():
    try:
        freq = psutil.cpu_freq()
    except (OSError, NotImplementedError):  # bazı sanal makinelerde yok
        return None
    return freq.current if freq else None


def cpu():
    per_core = psutil.cpu_percent(percpu=True)
    return {
        "total": round(sum(per_core) / len(per_core), 1),
        "per_core": per_core,
        "load_avg": psutil.getloadavg(),
        "freq_mhz": _cpu_freq_mhz(),
    }


def memory():
    m, s = psutil.virtual_memory(), psutil.swap_memory()
    return {
        "total": m.total,
        "used": m.total - m.available,
        "percent": m.percent,
        "swap_total": s.total,
        "swap_used": s.used,
        "swap_percent": s.percent,
    }


def disks():
    result = []
    for part in psutil.disk_partitions():
        if part.fstype in IGNORED_FSTYPES:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except OSError:  # yetki yok ya da sürücü hazır değil (boş CD vb.)
            continue
        result.append({"mount": part.mountpoint, "fstype": part.fstype,
                       "total": usage.total, "used": usage.used, "percent": usage.percent})
    return result


def temperatures():
    if not hasattr(psutil, "sensors_temperatures"):  # Windows/macOS'ta yok
        return []
    try:
        chips = psutil.sensors_temperatures()
    except OSError:
        return []
    return [{"chip": chip, "label": entry.label or chip,
             "current": entry.current, "high": entry.high or entry.critical}
            for chip, entries in chips.items() for entry in entries]


def processes():
    result = []
    for proc in psutil.process_iter(PROC_ATTRS):  # NoSuchProcess/AccessDenied'ı kendisi yakalar
        info = proc.info
        if info["pid"] == 0:  # Windows'taki "System Idle Process"
            continue
        mem = info["memory_info"]
        result.append({
            "pid": info["pid"],
            "name": info["name"] or "?",
            "username": info["username"] or "-",
            # htop gibi çekirdek başına değil, tüm CPU'ya oranla göster (toplam en fazla %100)
            "cpu_percent": round((info["cpu_percent"] or 0) / CPU_COUNT, 1),
            "memory_percent": round(info["memory_percent"] or 0, 1),
            "rss": mem.rss if mem else 0,
            "threads": info["num_threads"] or 0,
            "status": info["status"] or "-",
            "cmdline": " ".join(info["cmdline"] or []),
            "create_time": info["create_time"],
        })
    return result


def snapshot():
    return {
        "time": time.time(),
        "uptime": time.time() - psutil.boot_time(),
        "cpu": cpu(),
        "memory": memory(),
        "disks": disks(),
        "temps": temperatures(),
        "processes": processes(),
    }


if __name__ == "__main__":
    # Arayüz olmadan hızlı test: python collector.py
    import json

    snapshot()  # ilk cpu_percent ölçümü her zaman 0 döner
    time.sleep(1)
    data = snapshot()
    data["processes"] = sorted(data["processes"], key=lambda p: p["cpu_percent"], reverse=True)[:5]
    print(json.dumps(data, indent=2, ensure_ascii=False))
