
import logging

from PySide2.QtCore import Qt, QRect, QSize, QRectF
from PySide2.QtWidgets import QWidget
from PySide2.QtGui import QColor, QPainter, QBrush, QPen, QFont

from ..dsp import WAVEFORM_RESOLUTION

COLOR_FRAME = (40, 120, 40, 255)
COLOR_BACKGROND = (64, 64, 64, 255)
COLOR_WAVE = (128, 128, 128, 255)
COLOR_CURSOR = (255, 0, 0, 128)

CURSOR_WIDTH = 3

logger = logging.getLogger("waveform")

class WaveformCursorWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedSize(CURSOR_WIDTH, self.parent().height())

    def parent_resized(self):
        logger.debug("Resizing to match parent")
        self.setFixedSize(CURSOR_WIDTH, self.parent().height())
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        width = painter.device().width()
        height = painter.device().height()
        pen = QPen()
        pen.setColor(QColor(*COLOR_CURSOR))
        painter.setPen(pen)
        painter.drawRect(0, 0, width - 1, height - 1)

class WaveformWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cursor = WaveformCursorWidget(self)
        self._duration = 0
        self._waveform = None

    def set_duration(self, duration):
        self._duration = duration
        self.update()

    def set_waveform(self, waveform):
        self._waveform = waveform
        self.update()

    def set_cursor_position(self, time_pos):
        if time_pos < 0:
            logger.debug("Hiding cursor (requested pos: %r)", time_pos)
            self._cursor.hide()
            return
        cur_width = self._cursor.width()
        new_pos = WAVEFORM_RESOLUTION * time_pos
        logger.debug("Moving cursor to %r s %r px", time_pos, new_pos)
        self._cursor.move(new_pos + cur_width / 2, 0)
        self._cursor.show()

    def resizeEvent(self, event):
        self._cursor.parent_resized()

    def paintEvent(self, event):
        painter = QPainter(self)
        width = painter.device().width()
        height = painter.device().height()
        brush = QBrush()
        brush.setColor(QColor(*COLOR_BACKGROND))
        brush.setStyle(Qt.SolidPattern)
        pen = QPen()
        pen.setColor(QColor(*COLOR_FRAME))
        painter.setPen(pen)
        font = painter.font()
        font.setPixelSize(height / 6);
        painter.setFont(font);
        painter.fillRect(1, 1, width - 2, height - 2, brush)

        if self._waveform is not None:
            color = QColor(*COLOR_WAVE)
            for i, (w_min, w_max) in enumerate(self._waveform):
                x1 = x2 = i
                y1 = max((height - w_max * height) / 2, 0)
                y2 = min((height - w_min * height) / 2, height)
                rect = QRectF(x1, y1, 1, y2 - y1)
                painter.fillRect(rect, color)

        painter.drawRect(0, 0, width - 1, height - 1)
        painter.drawLine(0, height / 2, width - 1, height / 2)
        if self._duration:
            x = int(self._duration * WAVEFORM_RESOLUTION)
            painter.drawLine(x, 0, x, height - 1)
        for i in range(0, width // WAVEFORM_RESOLUTION):
            x = i * WAVEFORM_RESOLUTION
            if i > 0:
                painter.drawLine(x, height / 2 - 3 * pen.width(),
                                 x, height / 2 + 3 * pen.width())
            rect = QRect(x + 2 * pen.width(), height / 2 + 2 * pen.width(),
                         width, height)
            label = "{}s".format(i)
            painter.drawText(rect, Qt.AlignTop | Qt.AlignLeft, label)

    def minimumSizeHint(self):
        return QSize(100, 64)
