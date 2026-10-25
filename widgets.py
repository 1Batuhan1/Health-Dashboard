"""Arayüz bileşenleri: göstergeler, mini grafikler, kartlar ve satırlar.

Özel çizilen bileşenler renklerini her paintEvent'te `theme.current`'tan okur.
`refresh_theme()` metodu olan bileşenler tema değişince ana pencere tarafından çağrılır.
"""
from collections import deque

import pyqtgraph as pg
import qtawesome as qta
from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, Property
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

import theme


def icon(name, color_key="text_secondary"):
    return qta.icon(name, color=getattr(theme.current, color_key))


class IconLabel(QLabel):
    def __init__(self, name, color_key="text_secondary", size=18, parent=None):
        super().__init__(parent)
        self.icon_name, self.color_key, self.icon_size = name, color_key, size
        self.setFixedSize(size, size)
        self.refresh_theme()

    def refresh_theme(self):
        self.setPixmap(icon(self.icon_name, self.color_key).pixmap(self.icon_size, self.icon_size))


class Card(QFrame):
    """Yuvarlak köşeli, kenarlıklı yüzey (stili theme.py'deki #card kuralından gelir)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")


def styled_label(text="", object_name=None, font=None):
    label = QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    if font:
        label.setFont(font)
    return label


# --- Özel çizilen bileşenler ------------------------------------------------

class RingGauge(QWidget):
    """Dairesel yüzde göstergesi; değer değişince yumuşakça dolar."""

    def __init__(self, size=58, thickness=6, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.thickness = thickness
        self.color_key = "blue"
        self._value = 0.0
        self._animation = QPropertyAnimation(self, b"value", self)
        self._animation.setDuration(500)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)

    def _get_value(self):
        return self._value

    def _set_value(self, value):
        self._value = value
        self.update()

    value = Property(float, _get_value, _set_value)

    def animate_to(self, percent, color_key):
        self.color_key = color_key
        self._animation.stop()
        self._animation.setStartValue(self._value)
        self._animation.setEndValue(float(max(0, min(percent, 100))))
        self._animation.start()

    def paintEvent(self, event):
        t = theme.current
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        margin = self.thickness / 2 + 1
        rect = QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)

        pen = QPen(QColor(t.border), self.thickness)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)

        if self._value > 0.5:
            pen.setColor(QColor(getattr(t, self.color_key)))
            painter.setPen(pen)
            painter.drawArc(rect, 90 * 16, -int(self._value / 100 * 360 * 16))  # saat yönünde, tepeden


class Sparkline(QWidget):
    """Kart altındaki küçük eğilim grafiği."""

    def __init__(self, points=30, y_max=100, parent=None):  # 30 ölçüm ≈ son 1 dakika
        super().__init__(parent)
        self.setFixedHeight(36)
        self.points, self.y_max = points, y_max
        self.color_key = "blue"
        self.history = deque(maxlen=points)

    def add(self, value):
        self.history.append(value)
        self.update()

    def paintEvent(self, event):
        if len(self.history) < 2:
            return
        t = theme.current
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width, height = self.width(), self.height() - 3
        step = width / (self.points - 1)
        x0 = width - step * (len(self.history) - 1)  # sağdan dolsun
        points = [QPointF(x0 + i * step, 1.5 + height - min(v, self.y_max) / self.y_max * height)
                  for i, v in enumerate(self.history)]

        line = QPainterPath(points[0])
        for point in points[1:]:
            line.lineTo(point)
        area = QPainterPath(line)
        area.lineTo(points[-1].x(), self.height())
        area.lineTo(points[0].x(), self.height())
        area.closeSubpath()

        color = t.color(self.color_key)
        painter.fillPath(area, t.color(self.color_key, 0.14))
        painter.setPen(QPen(color, 1.8))
        painter.drawPath(line)


class LevelBar(QWidget):
    """İnce, yuvarlak uçlu doluluk çubuğu."""

    def __init__(self, height=8, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.color_key = "blue"
        self._value = 0.0

    def set_value(self, percent, color_key):
        self._value = max(0.0, min(percent, 100.0))
        self.color_key = color_key
        self.update()

    def paintEvent(self, event):
        t = theme.current
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        painter.setBrush(QColor(t.border))
        painter.drawRoundedRect(rect, radius, radius)
        if self._value > 0:
            fill = QRectF(rect)
            fill.setWidth(max(rect.width() * self._value / 100, rect.height()))
            painter.setBrush(QColor(getattr(t, self.color_key)))
            painter.drawRoundedRect(fill, radius, radius)


# --- Kartlar ------------------------------------------------------------------

class MetricCard(Card):
    """Özet kartı: simge + başlık, büyük değer, dairesel gösterge ve mini grafik."""

    def __init__(self, title, icon_name, color_key, parent=None):
        super().__init__(parent)
        self.icon = IconLabel(icon_name, color_key, 18)
        self.value = styled_label("—", font=theme.mono_font(19, QFont.Weight.Bold))
        self.detail = styled_label("", "muted")
        self.ring = RingGauge()
        self.ring.color_key = color_key
        self.spark = Sparkline()
        self.spark.color_key = color_key

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self.icon)
        header.addWidget(styled_label(title, "secondary"))
        header.addStretch()

        text = QVBoxLayout()
        text.setSpacing(2)
        text.addLayout(header)
        text.addSpacing(4)
        text.addWidget(self.value)
        text.addWidget(self.detail)

        row = QHBoxLayout()
        row.addLayout(text, 1)
        row.addWidget(self.ring, 0, Qt.AlignVCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 10)
        layout.setSpacing(8)
        layout.addLayout(row)
        layout.addWidget(self.spark)

    def set_values(self, value_text, percent, detail, color_key, history_value=None):
        self.value.setText(value_text)
        self.detail.setText(detail)
        self.ring.animate_to(percent, color_key)
        self.spark.color_key = color_key
        if history_value is not None:
            self.spark.add(history_value)


class HistoryChart(pg.PlotWidget):
    """Son N ölçümün alanı dolu çizgi grafiği."""

    def __init__(self, color_key, points=90, interval_s=2, y_max=100, parent=None):
        super().__init__(parent)
        self.color_key = color_key
        self.setYRange(0, y_max)
        self.setXRange(-(points - 1) * interval_s, 0)
        self.setMouseEnabled(False, False)
        self.setMenuEnabled(False)
        self.hideButtons()
        self.x = [(i - points + 1) * interval_s for i in range(points)]
        self.history = deque(maxlen=points)
        self.curve = self.plot([], [], fillLevel=0)
        self.refresh_theme()

    def add(self, value):
        self.history.append(value)
        self.curve.setData(self.x[-len(self.history):], list(self.history))

    def refresh_theme(self):
        t = theme.current
        _style_plot(self, t)
        self.setLabel("bottom", "saniye önce", color=t.muted)
        self.curve.setPen(pg.mkPen(t.color(self.color_key), width=2))
        self.curve.setBrush(t.color(self.color_key, 0.16))


class CoreBars(pg.PlotWidget):
    """Çekirdek başına anlık CPU kullanımı."""

    def __init__(self, count, color_key, parent=None):
        super().__init__(parent)
        self.color_key = color_key
        self.setYRange(0, 100)
        self.setXRange(-0.5, count - 0.5)
        self.setMouseEnabled(False, False)
        self.setMenuEnabled(False)
        self.hideButtons()
        self.getAxis("bottom").setTicks([[(i, str(i)) for i in range(count)]])
        self.bars = pg.BarGraphItem(x=list(range(count)), height=[0] * count, width=0.6)
        self.addItem(self.bars)
        self.refresh_theme()

    def set_values(self, values):
        self.bars.setOpts(height=values)

    def refresh_theme(self):
        t = theme.current
        _style_plot(self, t)
        color = t.color(self.color_key)
        self.bars.setOpts(brush=color, pen=pg.mkPen(color))


def _style_plot(plot, t):
    plot.setBackground(t.surface)
    for name in ("left", "bottom"):
        axis = plot.getAxis(name)
        axis.setPen(pg.mkPen(t.border))
        axis.setTextPen(pg.mkPen(t.muted))
    plot.showGrid(x=False, y=True, alpha=0.35)


class ChartCard(Card):
    """Başlıklı grafik kartı."""

    def __init__(self, title, subtitle, chart, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.addWidget(styled_label(title, "cardTitle"))
        layout.addWidget(styled_label(subtitle, "muted"))
        layout.addWidget(chart, 1)


class LevelRow(Card):
    """Disk ve sensör listelerindeki satır: simge, ad, değer ve doluluk çubuğu."""

    def __init__(self, icon_name, color_key, parent=None):
        super().__init__(parent)
        self.base_key = color_key
        self.title = styled_label("", "cardTitle")
        self.subtitle = styled_label("", "muted")
        self.info = styled_label("", "secondary", theme.mono_font(10))
        self.amount = styled_label("", font=theme.mono_font(14, QFont.Weight.Bold))
        self.bar = LevelBar(10)

        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(self.title)
        names.addWidget(self.subtitle)

        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(IconLabel(icon_name, color_key, 24))
        top.addLayout(names)
        top.addStretch()
        top.addWidget(self.info)
        top.addSpacing(12)
        top.addWidget(self.amount)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        layout.addLayout(top)
        layout.addWidget(self.bar)

    def set_values(self, title, subtitle, info, amount, percent, color_key):
        self.title.setText(title)
        self.subtitle.setText(subtitle)
        self.info.setText(info)
        self.amount.setText(amount)
        self.bar.set_value(percent, color_key)


class EmptyState(Card):
    def __init__(self, icon_name, title, body, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 40, 32, 40)
        layout.setSpacing(10)
        layout.addWidget(IconLabel(icon_name, "muted", 44), 0, Qt.AlignHCenter)
        title_label = styled_label(title, "cardTitle")
        body_label = styled_label(body, "muted")
        for label in (title_label, body_label):
            label.setAlignment(Qt.AlignCenter)
            label.setWordWrap(True)
            layout.addWidget(label)
