"""Koyu ve açık tema: renk paleti, Qt stil sayfası (QSS) ve yazı tipleri.

Özel çizilen bileşenler renkleri her çizimde `theme.current` üzerinden okur;
böylece tema değişince yalnızca yeniden çizilmeleri yeterli olur.
"""
from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont, QPalette


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    surface: str
    surface_alt: str
    border: str
    hover: str
    text: str
    text_secondary: str
    muted: str
    blue: str
    purple: str
    teal: str
    pink: str
    amber: str
    red: str
    green: str

    def color(self, key, alpha=None):
        color = QColor(getattr(self, key))
        if alpha is not None:
            color.setAlphaF(alpha)
        return color

    def soft(self, key, alpha=0.16):
        """QSS için yarı saydam renk: rgba(...)"""
        c = QColor(getattr(self, key))
        return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


DARK = Theme(
    name="dark", bg="#0f1115", surface="#171a21", surface_alt="#1e222b", border="#272c36",
    hover="#20242e", text="#e7e9ee", text_secondary="#a3abb9", muted="#6c7484",
    blue="#5b8cff", purple="#a78bfa", teal="#2dd4bf", pink="#f472b6",
    amber="#f5a524", red="#f2555a", green="#22c55e",
)
LIGHT = Theme(
    name="light", bg="#f4f5f7", surface="#ffffff", surface_alt="#f3f4f7", border="#e2e5ea",
    hover="#eef0f4", text="#111827", text_secondary="#4b5563", muted="#8b93a1",
    blue="#2563eb", purple="#7c3aed", teal="#0d9488", pink="#db2777",
    amber="#d97706", red="#dc2626", green="#16a34a",
)
THEMES = {"dark": DARK, "light": LIGHT}
current = DARK

# Listedeki ilk kurulu yazı tipi kullanılır (Kali/Debian: fonts-inter, fonts-jetbrains-mono)
UI_FONTS = ["Inter", "Segoe UI", "Cantarell", "Noto Sans", "DejaVu Sans"]
MONO_FONTS = ["JetBrains Mono", "Cascadia Mono", "Fira Mono", "DejaVu Sans Mono", "Consolas"]


def ui_font(point_size=10):
    font = QFont()
    font.setFamilies(UI_FONTS)
    font.setPointSizeF(point_size)
    return font


def mono_font(point_size=10, weight=QFont.Weight.Normal):
    font = QFont()
    font.setFamilies(MONO_FONTS)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSizeF(point_size)
    font.setWeight(weight)
    return font


def level_color(percent, base, warn=70, critical=90):
    """Değer eşikleri aşınca kategori rengi yerine uyarı rengini döndür."""
    if percent >= critical:
        return "red"
    if percent >= warn:
        return "amber"
    return base


def apply(app, name):
    global current
    current = THEMES[name]
    t = current

    palette = QPalette()
    for role, value in (
        (QPalette.Window, t.bg), (QPalette.WindowText, t.text),
        (QPalette.Base, t.surface), (QPalette.AlternateBase, t.surface_alt),
        (QPalette.Text, t.text), (QPalette.Button, t.surface_alt), (QPalette.ButtonText, t.text),
        (QPalette.Highlight, t.blue), (QPalette.HighlightedText, "#ffffff"),
        (QPalette.ToolTipBase, t.surface), (QPalette.ToolTipText, t.text),
        (QPalette.PlaceholderText, t.muted), (QPalette.Mid, t.border),
    ):
        palette.setColor(role, QColor(value))
    app.setPalette(palette)
    app.setStyleSheet(build_stylesheet(t))
    return t


def build_stylesheet(t):
    return f"""
    QMainWindow, #root, #page {{ background: {t.bg}; }}
    QWidget {{ color: {t.text}; }}
    QToolTip {{ background: {t.surface}; color: {t.text}; border: 1px solid {t.border};
                border-radius: 6px; padding: 4px 8px; }}

    #sidebar {{ background: {t.surface}; border-right: 1px solid {t.border}; }}
    #sidebar QToolButton {{ border: none; border-radius: 10px; padding: 10px; background: transparent; }}
    #sidebar QToolButton:hover {{ background: {t.hover}; }}
    #sidebar QToolButton:checked {{ background: {t.soft('blue')}; }}

    #card {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 14px; }}
    #pageTitle {{ font-size: 18pt; font-weight: 600; }}
    #cardTitle {{ font-size: 11pt; font-weight: 600; }}
    #secondary {{ color: {t.text_secondary}; }}
    #muted {{ color: {t.muted}; }}
    #live {{ color: {t.green}; font-weight: 600; }}

    QLineEdit {{ background: {t.surface_alt}; border: 1px solid {t.border}; border-radius: 8px;
                 padding: 6px 8px; selection-background-color: {t.blue}; }}
    QLineEdit:focus {{ border-color: {t.blue}; }}

    QTableView {{ background: transparent; border: none; outline: 0;
                  selection-background-color: {t.soft('blue', 0.20)}; selection-color: {t.text}; }}
    QTableView::item {{ border-bottom: 1px solid {t.border}; padding: 0 8px; }}
    QTableView::item:hover {{ background: {t.hover}; }}
    QTableView::item:selected {{ background: {t.soft('blue', 0.20)}; color: {t.text}; }}
    QHeaderView {{ background: transparent; }}
    QHeaderView::section {{ background: transparent; color: {t.muted}; border: none;
                            border-bottom: 1px solid {t.border}; padding: 8px; font-weight: 600; }}

    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {t.border}; border-radius: 3px; min-height: 30px; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {t.border}; border-radius: 3px; min-width: 30px; }}
    QScrollBar::handle:hover {{ background: {t.muted}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

    QMenu {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 10px; padding: 4px; }}
    QMenu::item {{ padding: 7px 18px 7px 10px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {t.soft('blue')}; }}

    QPushButton {{ background: {t.surface_alt}; border: 1px solid {t.border}; border-radius: 8px;
                   padding: 6px 16px; }}
    QPushButton:hover {{ background: {t.hover}; }}
    QMessageBox {{ background: {t.surface}; }}
    """
