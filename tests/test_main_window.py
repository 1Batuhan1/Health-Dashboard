"""End-to-end check: build the real window and feed it real data, without a display."""
import pytest
from PySide6.QtCore import QSettings, QThread

import collector
import main
import theme


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    # Don't start the background thread; the test drives updates itself
    monkeypatch.setattr(main.MainWindow, "_start_worker", lambda self: setattr(self, "worker_thread", QThread()))
    theme.apply(qapp, "dark")
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    win = main.MainWindow(settings, save_theme=False)
    yield win
    win.close()


def test_update_fills_every_page(window):
    collector.snapshot()
    data = collector.snapshot()
    window.on_update(data)

    assert window.process_model.rowCount() == len(data["processes"])
    assert window.page_subtitle.text().startswith(window.hostname)
    assert "up " in window.page_subtitle.text()
    assert window.cpu_card.value.text().endswith("%")
    assert len(window._disk_rows) == len(data["disks"])
    assert window.temp_empty.isHidden() == bool(data["temps"])


@pytest.mark.parametrize(("index", "title"), list(enumerate(["Overview", "Performance", "Disks", "Temperatures"])))
def test_sidebar_pages(window, index, title):
    window.show_page(index)
    assert window.stack.currentIndex() == index
    assert window.page_title.text() == title


def test_toggle_theme_switches_and_back(window):
    window.toggle_theme()
    assert theme.current.name == "light"
    window.toggle_theme()
    assert theme.current.name == "dark"
