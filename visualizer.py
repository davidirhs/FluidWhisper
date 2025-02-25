from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QPolygonF
from PySide6.QtCore import QTimer, Qt, QPointF
import numpy as np

class WaveformWidget(QWidget):
    def __init__(self, width=400, height=60):
        super().__init__()
        self.setMinimumSize(width, height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.width = width
        self.height = height
        self.wave_color = QColor(200, 200, 200)  # Light grey for the waveform
        self.amplitudes = [0] * self.width
        self.mode = 'recording'
        self.phase = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_waveform)
        self.timer.start(50)  # Update every 50 ms
        self.animation_timer = None

    def set_mode(self, mode):
        self.mode = mode
        if mode == 'processing':
            if not self.animation_timer:
                self.animation_timer = QTimer(self)
                self.animation_timer.timeout.connect(self.update_phase)
                self.animation_timer.start(30)
        elif self.animation_timer:
            self.animation_timer.stop()
            self.animation_timer = None
            self.phase = 0

    def update_phase(self):
        self.phase += 0.3
        self.update()

    def update_waveform(self):
        if self.mode == 'recording':
            self.update()

    def push_amplitude(self, amplitude):
        if self.mode == 'recording':
            # Scale non-negative amplitude to use full height, matching old sensitivity
            scaled_amplitude = min(amplitude / 0.3, 1.0)  # Cap at 1.0, using /0.3 for sensitivity
            self.amplitudes.append(scaled_amplitude)
            if len(self.amplitudes) > self.width:
                self.amplitudes.pop(0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(30, 30, 30))  # Dark grey background

        points = []

        if self.mode == 'recording':
            # Use full height for non-negative amplitudes, starting from bottom
            base_y = self.height  # Start at the bottom
            for x, amp in enumerate(self.amplitudes[-self.width:]):
                # Scale amplitude to fill the height (0 at bottom, 1 at top)
                y = base_y - (amp * self.height)  # Invert so larger amplitudes go higher
                points.append(QPointF(x, y))
        else:  # Processing mode
            mid_y = self.height // 2
            for x in range(self.width):
                amp = 0.5 + 0.45 * np.sin((x / 15) + (self.phase % (2 * np.pi)))
                y = mid_y - (amp * (self.height * 0.4))
                points.append(QPointF(x, y))

        # Close the polygon for filling (from bottom to bottom)
        points.append(QPointF(self.width, self.height))
        points.append(QPointF(0, self.height))
        polygon = QPolygonF(points)

        # Gradient for waveform fill (light grey to transparent, bottom to top)
        gradient = QLinearGradient(0, self.height, 0, 0)  # Gradient from bottom (dark) to top (transparent)
        gradient.setColorAt(0, self.wave_color)
        gradient.setColorAt(1, Qt.transparent)
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(polygon)

    def stop(self):
        self.timer.stop()
        if self.animation_timer:
            self.animation_timer.stop()