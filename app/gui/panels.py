from __future__ import annotations

import datetime as dt
from collections import deque
from typing import Callable

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from app.core.models import Obstacle, Telemetry, VisionObstacle


class TelemetryPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Telemetry")
        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(10)

        self.battery_value = self._make_value_label("100.0 %")
        self.xyz_value = self._make_value_label("x=0.00 y=0.00 z=0.00 m")
        self.rpy_value = self._make_value_label("r=0.00 p=0.00 y=0.00 deg")
        self.vel_value = self._make_value_label("vx=0.00 vy=0.00 vz=0.00 m/s")
        self.mode_value = self._make_value_label("AUTO")
        self.ultra_value = self._make_value_label("999.0 cm")
        self.vision_value = self._make_value_label("clear")

        layout.addRow("Battery", self.battery_value)
        layout.addRow("Position", self.xyz_value)
        layout.addRow("Attitude", self.rpy_value)
        layout.addRow("Velocity", self.vel_value)
        layout.addRow("Mode", self.mode_value)
        layout.addRow("Ultrasonic", self.ultra_value)
        layout.addRow("Vision", self.vision_value)

    def update_values(self, telemetry: Telemetry, obstacle: Obstacle, vision: VisionObstacle) -> None:
        self.battery_value.setText(f"{telemetry.battery_pct:.1f} %")
        self.xyz_value.setText(f"x={telemetry.x:.2f} y={telemetry.y:.2f} z={telemetry.z:.2f} m")
        self.rpy_value.setText(f"r={telemetry.roll:.2f} p={telemetry.pitch:.2f} y={telemetry.yaw:.2f} deg")
        self.vel_value.setText(f"vx={telemetry.vx:.2f} vy={telemetry.vy:.2f} vz={telemetry.vz:.2f} m/s")
        self.mode_value.setText(telemetry.mode)
        self.ultra_value.setText(f"{obstacle.ultrasonic_cm:.1f} cm ({obstacle.risk})")

        if vision.detected:
            self.vision_value.setText(f"DETECTED: {vision.label}")
            self.vision_value.setStyleSheet("font-size: 14px; font-weight: 700; color: #b71c1c;")
        else:
            self.vision_value.setText("clear")
            self.vision_value.setStyleSheet("font-size: 14px; font-weight: 700; color: #2e7d32;")

    def _make_value_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("ValueLabel")
        label.setMinimumWidth(230)
        return label


class PlotsPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Plots")
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._battery_history: deque[float] = deque(maxlen=500)
        self._ultra_history: deque[float] = deque(maxlen=500)

        self.battery_plot = self._create_plot("Battery %", (50, 132, 107), (0, 100))
        self.battery_curve = self.battery_plot.plot(pen=pg.mkPen(color=(50, 132, 107), width=2))

        self.ultra_plot = self._create_plot("Ultrasonic Distance (cm)", (180, 103, 53), (0, 250))
        self.ultra_curve = self.ultra_plot.plot(pen=pg.mkPen(color=(180, 103, 53), width=2))

        layout.addWidget(self.battery_plot)
        layout.addWidget(self.ultra_plot)

    def push_battery(self, value: float) -> None:
        self._battery_history.append(value)
        self.battery_curve.setData(list(self._battery_history))

    def push_ultrasonic(self, value: float) -> None:
        self._ultra_history.append(value)
        self.ultra_curve.setData(list(self._ultra_history))

    def _create_plot(self, title: str, line_color: tuple[int, int, int], y_range: tuple[int, int]) -> pg.PlotWidget:
        plot = pg.PlotWidget(title=title)
        plot.setYRange(*y_range)
        plot.showGrid(x=True, y=True, alpha=0.18)
        plot.setBackground("#fff9f2")
        axis_pen = pg.mkPen(color=line_color, width=1)
        plot.getAxis("left").setPen(axis_pen)
        plot.getAxis("bottom").setPen(axis_pen)
        return plot


class CameraPanel(QGroupBox):
    def __init__(self, on_start: Callable[[], None], on_stop: Callable[[], None]) -> None:
        super().__init__("Camera")
        layout = QVBoxLayout(self)

        self.source_input = QLineEdit("auto")
        self.source_input.setPlaceholderText("auto, webcam:0, 0, or http://...")

        self.start_btn = QPushButton("Start Camera Detection")
        self.stop_btn = QPushButton("Stop Detection")
        self.stop_btn.setObjectName("NeutralButton")
        self.start_btn.clicked.connect(on_start)
        self.stop_btn.clicked.connect(on_stop)

        self.status_label = QLabel("Vision: stopped")
        self.status_label.setStyleSheet("font-weight: 700; color: #4a443e;")

        self.preview_label = QLabel("Camera preview will appear here")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedHeight(300)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.preview_label.setStyleSheet(
            "border: 1px solid #d8ccb8; border-radius: 10px; background: #fff9f2; color: #4a443e;"
        )

        source_form = QFormLayout()
        source_form.setContentsMargins(0, 0, 0, 0)
        source_form.addRow("Source", self.source_input)

        button_row = QHBoxLayout()
        button_row.addWidget(self.start_btn)
        button_row.addWidget(self.stop_btn)

        layout.addLayout(source_form)
        layout.addLayout(button_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.preview_label)

    def source_text(self) -> str:
        return self.source_input.text().strip()

    def set_status(self, status: str) -> None:
        self.status_label.setText(f"Vision: {status}")

    def set_preview(self, frame_jpeg: bytes) -> None:
        image = QImage.fromData(frame_jpeg, "JPG")
        if image.isNull():
            return

        pixmap = QPixmap.fromImage(image)
        target_w = max(1, self.preview_label.width())
        target_h = max(1, self.preview_label.height())
        scaled = pixmap.scaled(
            target_w,
            target_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        canvas = QPixmap(target_w, target_h)
        canvas.fill(QColor("#fff9f2"))
        painter = QPainter(canvas)
        draw_x = (target_w - scaled.width()) // 2
        draw_y = (target_h - scaled.height()) // 2
        painter.drawPixmap(draw_x, draw_y, scaled)
        painter.end()

        self.preview_label.setPixmap(canvas)


class ActionPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Action")
        layout = QVBoxLayout(self)

        self.action_label = QLabel("Normal operation.")
        self.action_label.setWordWrap(True)
        self.action_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.action_label.setMinimumHeight(96)
        self.action_label.setStyleSheet(
            """
            QLabel {
                border: 1px solid #d8ccb8;
                border-radius: 10px;
                background: #fcf6ec;
                padding: 12px;
                font-size: 14px;
                color: #39342f;
            }
            """
        )
        layout.addWidget(self.action_label)

    def set_action(self, text: str) -> None:
        if self.action_label.text() != text:
            self.action_label.setText(text)


class EventsPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Events")
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

    def append_event(self, level: str, text: str, ts: float | None = None) -> None:
        timestamp = dt.datetime.fromtimestamp(ts) if ts else dt.datetime.now()
        item = QListWidgetItem(f"[{timestamp.strftime('%H:%M:%S')}] {level.upper()} - {text}")
        if level.lower() in {"warn", "warning"}:
            item.setForeground(QColor("#ef6c00"))
        elif level.lower() in {"error", "critical"}:
            item.setForeground(QColor("#b71c1c"))

        self.list_widget.insertItem(0, item)
        if self.list_widget.count() > 200:
            self.list_widget.takeItem(self.list_widget.count() - 1)
