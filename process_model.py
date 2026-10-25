from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

import theme
from formatting import format_bytes

SORT_ROLE = Qt.UserRole

COLUMNS = [
    ("PID", "pid"),
    ("İsim", "name"),
    ("Kullanıcı", "username"),
    ("CPU %", "cpu_percent"),
    ("Bellek", "rss"),
    ("RAM %", "memory_percent"),
    ("Thread", "threads"),
    ("Durum", "status"),
    ("Komut", "cmdline"),
]
CPU_COLUMN = 3
STATUS_COLUMN = 7
RIGHT_ALIGNED_KEYS = {"pid", "rss", "memory_percent", "threads"}
MONO_KEYS = RIGHT_ALIGNED_KEYS | {"cpu_percent"}

# Turkish labels for psutil status names (search also matches these labels)
STATUS_LABELS = {
    "running": "çalışıyor",
    "sleeping": "uyuyor",
    "idle": "boşta",
    "disk-sleep": "G/Ç bekliyor",
    "stopped": "durdu",
    "tracing-stop": "izleniyor",
    "zombie": "zombi",
    "dead": "öldü",
    "waking": "uyanıyor",
    "parked": "park",
}


class ProcessModel(QAbstractTableModel):
    """Process list. Instead of resetting the table on every refresh, rows are
    updated by PID, so the selected row and scroll position are kept."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.mono_font = theme.mono_font(9.5)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation != Qt.Horizontal:
            return None
        if role == Qt.DisplayRole:
            return COLUMNS[section][0]
        if role == Qt.TextAlignmentRole:
            if COLUMNS[section][1] in RIGHT_ALIGNED_KEYS:
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        key = COLUMNS[index.column()][1]
        value = self.rows[index.row()][key]
        if role == Qt.DisplayRole:
            if key == "rss":
                return format_bytes(value)
            if key in ("cpu_percent", "memory_percent"):
                return f"{value:.1f}"
            if key == "status":
                return STATUS_LABELS.get(value, value)
            return str(value)
        if role == SORT_ROLE:
            return value
        if role == Qt.TextAlignmentRole:
            if key in RIGHT_ALIGNED_KEYS:
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        if role == Qt.FontRole and key in MONO_KEYS:
            return self.mono_font
        if role == Qt.ToolTipRole and key == "cmdline":
            return value or None
        return None

    def row_at(self, row):
        return self.rows[row]

    def update(self, processes):
        incoming = {p["pid"]: p for p in processes}

        # Remove processes that have exited and update the remaining ones in place
        for row in range(len(self.rows) - 1, -1, -1):
            pid = self.rows[row]["pid"]
            if pid in incoming:
                self.rows[row] = incoming.pop(pid)
            else:
                self.beginRemoveRows(QModelIndex(), row, row)
                del self.rows[row]
                self.endRemoveRows()
        if self.rows:
            self.dataChanged.emit(self.index(0, 0),
                                  self.index(len(self.rows) - 1, len(COLUMNS) - 1))

        # Add newly started processes
        if incoming:
            start = len(self.rows)
            self.beginInsertRows(QModelIndex(), start, start + len(incoming) - 1)
            self.rows.extend(incoming.values())
            self.endInsertRows()
