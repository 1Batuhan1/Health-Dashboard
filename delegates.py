"""Process tablosundaki özel hücreler: renkli CPU çubuğu ve durum etiketi."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

import theme
from process_model import SORT_ROLE

STATUS_COLORS = {
    "running": "green",
    "sleeping": "text_secondary",
    "idle": "text_secondary",
    "disk-sleep": "amber",
    "stopped": "amber",
    "tracing-stop": "amber",
    "zombie": "red",
    "dead": "red",
}


def _draw_background(option, index, painter, delegate):
    """Seçim ve hover arka planını stile çizdir, metni biz çizeceğiz."""
    opt = QStyleOptionViewItem(option)
    delegate.initStyleOption(opt, index)
    text = opt.text
    opt.text = ""
    style = opt.widget.style() if opt.widget else QApplication.style()
    style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)
    return opt, text


class CpuBarDelegate(QStyledItemDelegate):
    """CPU yüzdesinin yanında yüke göre maviden turuncuya ve kırmızıya dönen çubuk."""

    WARN, CRITICAL = 10, 40  # toplam CPU'ya oranlı: 8 çekirdekte tek çekirdeği dolduran ≈ %12,5

    def paint(self, painter, option, index):
        opt, text = _draw_background(option, index, painter, self)
        value = index.data(SORT_ROLE) or 0
        t = theme.current

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(10, 0, -10, 0)
        text_width = 40
        track = QRectF(rect.left(), rect.center().y() - 3, max(rect.width() - text_width - 10, 10), 6)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(t.border))
        painter.drawRoundedRect(track, 3, 3)
        if value > 0:
            key = "red" if value >= self.CRITICAL else "amber" if value >= self.WARN else "blue"
            fill = QRectF(track)
            fill.setWidth(max(track.width() * min(value, 100) / 100, 6))
            painter.setBrush(QColor(getattr(t, key)))
            painter.drawRoundedRect(fill, 3, 3)

        painter.setPen(QColor(t.text))
        painter.setFont(opt.font)
        painter.drawText(QRectF(rect.right() - text_width, rect.top(), text_width, rect.height()),
                         Qt.AlignRight | Qt.AlignVCenter, text)
        painter.restore()


class StatusDelegate(QStyledItemDelegate):
    """Durumu renkli, yuvarlak bir etiket olarak gösterir."""

    def paint(self, painter, option, index):
        opt, text = _draw_background(option, index, painter, self)
        key = STATUS_COLORS.get(index.data(SORT_ROLE), "text_secondary")
        t = theme.current

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        font = QApplication.font()
        font.setPointSizeF(font.pointSizeF() * 0.9)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        height = metrics.height() + 6
        pill = QRectF(option.rect.left() + 8, option.rect.center().y() - height / 2 + 0.5,
                      metrics.horizontalAdvance(text) + 20, height)
        painter.setPen(Qt.NoPen)
        painter.setBrush(t.color(key, 0.16))
        painter.drawRoundedRect(pill, height / 2, height / 2)
        painter.setPen(t.color(key))
        painter.drawText(pill, Qt.AlignCenter, text)
        painter.restore()
