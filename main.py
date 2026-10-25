"""SysDash: Linux sistem sağlığı masaüstü uygulaması.

Çalıştırma:  python main.py
Geliştirme:  python main.py --screenshot ekran.png --page 0 --theme light
             (birkaç yenilemeden sonra görüntü alıp kapanır)
"""
import argparse
import os
import socket
import sys

import psutil
import pyqtgraph as pg
from PySide6.QtCore import (QObject, QSettings, QSize, QSortFilterProxyModel, Qt, QThread,
                            QTimer, Signal, Slot)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QFrame,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QMainWindow, QMenu, QMessageBox, QScrollArea, QStackedWidget,
                               QTableView, QToolButton, QVBoxLayout, QWidget)

import collector
import theme
from delegates import CpuBarDelegate, StatusDelegate
from formatting import format_bytes, format_duration
from process_model import CPU_COLUMN, SORT_ROLE, STATUS_COLUMN, ProcessModel
from widgets import (Card, ChartCard, CoreBars, EmptyState, HistoryChart, IconLabel, LevelRow,
                     MetricCard, icon, styled_label)

REFRESH_MS = 2000
ROOT_MOUNT = os.path.abspath(os.sep)  # Linux'ta "/", Windows'ta "C:\"
PAGES = [
    ("Genel bakış", "mdi6.view-dashboard-outline"),
    ("Performans", "mdi6.chart-line"),
    ("Diskler", "mdi6.harddisk"),
    ("Sıcaklıklar", "mdi6.thermometer"),
]


class CollectorWorker(QObject):
    """Veriyi arka plan thread'inde toplar; arayüz donmaz."""

    updated = Signal(dict)

    @Slot()
    def start(self):
        collector.snapshot()  # ilk cpu_percent ölçümü 0 döner, onu at
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.collect)
        self.timer.start(REFRESH_MS)
        QTimer.singleShot(500, self.collect)

    @Slot()
    def collect(self):
        self.updated.emit(collector.snapshot())


class MainWindow(QMainWindow):
    def __init__(self, settings, save_theme=True):
        super().__init__()
        self.settings = settings
        self.save_theme = save_theme
        self.setWindowTitle("SysDash — Sistem Sağlığı")
        self.setWindowIcon(icon("mdi6.pulse", "blue"))
        self.resize(1240, 800)
        self.setMinimumSize(1000, 680)
        self.hostname = socket.gethostname()
        self._disk_rows, self._sensor_rows = {}, {}

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_overview_page())
        self.stack.addWidget(self._build_performance_page())
        self.stack.addWidget(self._build_disk_page())
        self.stack.addWidget(self._build_temp_page())

        self.page_title = styled_label(PAGES[0][0], "pageTitle")
        self.page_subtitle = styled_label("Veriler toplanıyor…", "muted")
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(self.page_title)
        titles.addWidget(self.page_subtitle)
        header = QHBoxLayout()
        header.addLayout(titles)
        header.addStretch()
        header.addWidget(styled_label("●  Canlı", "live"))

        content = QVBoxLayout()
        content.setContentsMargins(24, 20, 24, 20)
        content.setSpacing(16)
        content.addLayout(header)
        content.addWidget(self.stack, 1)

        root = QWidget()
        root.setObjectName("root")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())
        layout.addLayout(content, 1)
        self.setCentralWidget(root)

        self._show_page(0)
        self._start_worker()

    # --- Yan menü -----------------------------------------------------------

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(68)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(11, 18, 11, 18)
        layout.setSpacing(6)
        layout.addWidget(IconLabel("mdi6.pulse", "blue", 28), 0, Qt.AlignHCenter)
        layout.addSpacing(18)

        self.nav_group = QButtonGroup(self)
        self.nav_buttons = []
        for index, (title, icon_name) in enumerate(PAGES):
            button = self._sidebar_button(title)
            button.setCheckable(True)
            self.nav_group.addButton(button, index)
            self.nav_buttons.append((button, icon_name))
            layout.addWidget(button, 0, Qt.AlignHCenter)
        self.nav_group.idClicked.connect(self._show_page)

        layout.addStretch()
        self.theme_button = self._sidebar_button("Temayı değiştir")
        self.theme_button.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_button, 0, Qt.AlignHCenter)
        return sidebar

    @staticmethod
    def _sidebar_button(tooltip):
        button = QToolButton()
        button.setToolTip(tooltip)
        button.setIconSize(QSize(22, 22))
        button.setCursor(Qt.PointingHandCursor)
        return button

    def _refresh_sidebar_icons(self):
        for button, icon_name in self.nav_buttons:
            button.setIcon(icon(icon_name, "blue" if button.isChecked() else "muted"))
        sun_or_moon = "mdi6.white-balance-sunny" if theme.current.name == "dark" else "mdi6.weather-night"
        self.theme_button.setIcon(icon(sun_or_moon, "muted"))
        self.search.removeAction(self.search_action)
        self.search_action = self.search.addAction(icon("mdi6.magnify", "muted"), QLineEdit.LeadingPosition)

    def _show_page(self, index):
        self.nav_group.button(index).setChecked(True)
        self.stack.setCurrentIndex(index)
        self.page_title.setText(PAGES[index][0])
        self._refresh_sidebar_icons()

    def toggle_theme(self):
        name = "light" if theme.current.name == "dark" else "dark"
        theme.apply(QApplication.instance(), name)
        if self.save_theme:
            self.settings.setValue("theme", name)
        for widget in self.findChildren(QWidget):
            if hasattr(widget, "refresh_theme"):
                widget.refresh_theme()
            widget.update()
        self._refresh_sidebar_icons()

    # --- Sayfalar -----------------------------------------------------------

    def _build_overview_page(self):
        self.cpu_card = MetricCard("CPU", "mdi6.chip", "blue")
        self.ram_card = MetricCard("RAM", "mdi6.memory", "purple")
        self.disk_card = MetricCard("Disk", "mdi6.harddisk", "teal")
        self.temp_card = MetricCard("Sıcaklık", "mdi6.thermometer", "pink")
        cards = QHBoxLayout()
        cards.setSpacing(14)
        for card in (self.cpu_card, self.ram_card, self.disk_card, self.temp_card):
            cards.addWidget(card, 1)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(cards)
        layout.addWidget(self._build_process_card(), 1)
        return page

    def _build_process_card(self):
        self.process_model = ProcessModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.process_model)
        self.proxy.setSortRole(SORT_ROLE)
        self.proxy.setFilterKeyColumn(-1)  # tüm sütunlarda ara
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.search = QLineEdit(placeholderText="İsim, kullanıcı, PID veya komut ara")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(300)
        self.search_action = self.search.addAction(icon("mdi6.magnify", "muted"), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setItemDelegateForColumn(CPU_COLUMN, CpuBarDelegate(self.table))
        self.table.setItemDelegateForColumn(STATUS_COLUMN, StatusDelegate(self.table))
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(CPU_COLUMN, Qt.DescendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setMouseTracking(True)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(36)
        header = self.table.horizontalHeader()
        header.setHighlightSections(False)
        header.setStretchLastSection(True)
        for column, width in enumerate((76, 190, 130, 160, 96, 72, 72, 130)):
            self.table.setColumnWidth(column, width)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_process_menu)

        self.process_count = styled_label("", "muted")
        top = QHBoxLayout()
        top.addWidget(styled_label("Processler", "cardTitle"))
        top.addWidget(self.process_count)
        top.addStretch()
        top.addWidget(self.search)

        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 8)
        layout.setSpacing(10)
        layout.addLayout(top)
        layout.addWidget(self.table, 1)
        return card

    def _build_performance_page(self):
        interval = REFRESH_MS // 1000
        self.cpu_chart = HistoryChart("blue", interval_s=interval)
        self.ram_chart = HistoryChart("purple", interval_s=interval)
        self.core_bars = CoreBars(collector.CPU_COUNT, "blue")

        page = QWidget()
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(ChartCard("CPU kullanımı", "Son 3 dakika, %", self.cpu_chart), 0, 0)
        layout.addWidget(ChartCard("RAM kullanımı", "Son 3 dakika, %", self.ram_chart), 0, 1)
        layout.addWidget(ChartCard("Çekirdekler", "Çekirdek başına anlık kullanım, %", self.core_bars), 1, 0, 1, 2)
        return page

    def _build_disk_page(self):
        self.disk_list = QVBoxLayout()
        self.disk_list.setSpacing(12)
        return self._scroll_page(self.disk_list)

    def _build_temp_page(self):
        self.temp_empty = EmptyState(
            "mdi6.thermometer-off", "Sıcaklık sensörü bulunamadı",
            "Sanal makinede, WSL'de ve Windows'ta bu normaldir. Fiziksel bir Linux "
            "makinede lm-sensors paketini kurup 'sudo sensors-detect' çalıştırmayı dene.")
        self.sensor_list = QVBoxLayout()
        self.sensor_list.setSpacing(12)
        self.sensor_list.addWidget(self.temp_empty)
        return self._scroll_page(self.sensor_list)

    @staticmethod
    def _scroll_page(list_layout):
        container = QWidget()
        container.setObjectName("page")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.addLayout(list_layout)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(container)
        return scroll

    # --- Veri akışı ---------------------------------------------------------

    def _start_worker(self):
        # Not: QObject.thread() metodunu gölgelememek için adı worker_thread
        self.worker_thread = QThread(self)
        self.worker = CollectorWorker()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.start)
        # Arayüze yalnızca ana thread dokunabilir; bağlantıyı açıkça kuyruklu yap
        self.worker.updated.connect(self.on_update, Qt.QueuedConnection)
        self.worker_thread.start()

    @Slot(dict)
    def on_update(self, data):
        cpu, mem = data["cpu"], data["memory"]

        freq = f" · {cpu['freq_mhz'] / 1000:.2f} GHz" if cpu["freq_mhz"] else ""
        self.cpu_card.set_values(f"%{cpu['total']:.1f}", cpu["total"],
                                 f"{collector.CPU_COUNT} çekirdek{freq}",
                                 theme.level_color(cpu["total"], "blue"), cpu["total"])
        swap = f" · swap %{mem['swap_percent']:.0f}" if mem["swap_total"] else ""
        self.ram_card.set_values(f"%{mem['percent']:.1f}", mem["percent"],
                                 f"{format_bytes(mem['used'])} / {format_bytes(mem['total'])}{swap}",
                                 theme.level_color(mem["percent"], "purple", 80, 92), mem["percent"])
        self._update_disk_card(data["disks"])
        self._update_temp_card(data["temps"])

        self.process_model.update(data["processes"])
        self.process_count.setText(f"· {len(data['processes'])}")

        self.cpu_chart.add(cpu["total"])
        self.ram_chart.add(mem["percent"])
        self.core_bars.set_values(cpu["per_core"])
        self._update_disk_rows(data["disks"])
        self._update_sensor_rows(data["temps"])

        load = " ".join(f"{x:.2f}" for x in cpu["load_avg"])
        self.page_subtitle.setText(f"{self.hostname}  ·  çalışma süresi {format_duration(data['uptime'])}"
                                   f"  ·  yük {load}")

    def _update_disk_card(self, disks):
        disk = next((d for d in disks if d["mount"] == ROOT_MOUNT), disks[0] if disks else None)
        if disk is None:
            self.disk_card.set_values("—", 0, "Disk bulunamadı", "teal")
            return
        self.disk_card.set_values(f"%{disk['percent']:.0f}", disk["percent"],
                                  f"{disk['mount']} · {format_bytes(disk['used'])} / {format_bytes(disk['total'])}",
                                  theme.level_color(disk["percent"], "teal", 80, 90), disk["percent"])

    def _update_temp_card(self, temps):
        if not temps:
            self.temp_card.set_values("—", 0, "Sensör bulunamadı", "pink")
            return
        hottest = max(temps, key=lambda t: t["current"])
        self.temp_card.set_values(f"{hottest['current']:.0f} °C", hottest["current"], hottest["label"],
                                  theme.level_color(hottest["current"], "pink", 70, 85), hottest["current"])

    def _sync_rows(self, rows, list_layout, keys, factory):
        """Disk/sensör listesi değiştiyse satırları ekle ya da çıkar."""
        for key in list(rows):
            if key not in keys:
                rows.pop(key).deleteLater()
        for key in keys:
            if key not in rows:
                rows[key] = factory()
                list_layout.addWidget(rows[key])
                rows[key].show()  # görünür bir sayfaya sonradan eklenen widget kendiliğinden görünmez

    def _update_disk_rows(self, disks):
        self._sync_rows(self._disk_rows, self.disk_list, [d["mount"] for d in disks],
                        lambda: LevelRow("mdi6.harddisk", "teal"))
        for d in disks:
            self._disk_rows[d["mount"]].set_values(
                d["mount"], d["fstype"],
                f"{format_bytes(d['used'])} / {format_bytes(d['total'])}", f"%{d['percent']:.0f}",
                d["percent"], theme.level_color(d["percent"], "teal", 80, 90))

    def _update_sensor_rows(self, temps):
        self.temp_empty.setVisible(not temps)
        keys = [f"{t['chip']}/{t['label']}" for t in temps]
        self._sync_rows(self._sensor_rows, self.sensor_list, keys,
                        lambda: LevelRow("mdi6.thermometer", "pink"))
        for key, t in zip(keys, temps):
            limit = t["high"] or 100
            self._sensor_rows[key].set_values(
                t["label"], t["chip"], f"üst sınır {limit:.0f} °C", f"{t['current']:.0f} °C",
                t["current"] / limit * 100, theme.level_color(t["current"], "pink", 70, 85))

    # --- Process işlemleri --------------------------------------------------

    def _show_process_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        proc = self.process_model.row_at(self.proxy.mapToSource(index).row())

        menu = QMenu(self)
        terminate = menu.addAction(icon("mdi6.close-circle-outline", "amber"), "Sonlandır (SIGTERM)")
        kill = menu.addAction(icon("mdi6.skull-outline", "red"), "Zorla öldür (SIGKILL)")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is terminate:
            self._stop_process(proc, force=False)
        elif chosen is kill:
            self._stop_process(proc, force=True)

    def _stop_process(self, proc, force):
        verb = "zorla öldürülsün" if force else "sonlandırılsın"
        answer = QMessageBox.question(self, "Process'i durdur",
                                      f"{proc['name']} (PID {proc['pid']}) {verb} mi?")
        if answer != QMessageBox.Yes:
            return
        try:
            p = psutil.Process(proc["pid"])
            if p.create_time() != proc["create_time"]:  # PID bu arada başka bir process'e geçmiş
                return
            if force:
                p.kill()
            else:
                p.terminate()
        except psutil.NoSuchProcess:
            pass  # zaten kapanmış
        except psutil.AccessDenied:
            QMessageBox.warning(self, "Yetki yok",
                                "Bu process başka bir kullanıcıya ait.\n"
                                f"Linux'ta terminalden 'pkexec kill {proc['pid']}' ile durdurabilirsin.")

    def closeEvent(self, event):
        self.worker_thread.quit()
        self.worker_thread.wait()
        super().closeEvent(event)


def main():
    parser = argparse.ArgumentParser(description="SysDash sistem sağlığı uygulaması")
    parser.add_argument("--theme", choices=["dark", "light"], help="kayıtlı temayı bu açılış için geçersiz kıl")
    parser.add_argument("--page", type=int, default=0, help="açılışta gösterilecek sayfa (0-3)")
    parser.add_argument("--screenshot", metavar="DOSYA",
                        help="birkaç yenilemeden sonra pencere görüntüsünü kaydet ve kapan")
    parser.add_argument("--delay", type=float, default=9, help="--screenshot için bekleme süresi (saniye)")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("SysDash")
    app.setDesktopFileName("sysdash")  # Wayland'de .desktop dosyası ve simgeyle eşleşir
    app.setStyle("Fusion")
    app.setFont(theme.ui_font(10))
    pg.setConfigOptions(antialias=True)

    settings = QSettings("SysDash", "SysDash")
    system_light = app.styleHints().colorScheme() == Qt.ColorScheme.Light
    theme_name = args.theme or settings.value("theme") or ("light" if system_light else "dark")
    theme.apply(app, theme_name)

    window = MainWindow(settings, save_theme=args.theme is None)
    window._show_page(args.page)
    window.show()

    if args.screenshot:
        def grab_and_close():
            window.grab().save(args.screenshot)
            window.close()
        QTimer.singleShot(int(args.delay * 1000), grab_and_close)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
