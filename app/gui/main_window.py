from __future__ import annotations

import datetime as dt
import queue
from collections import deque

import pyqtgraph as pg
from PyQt6.QtCore import QTimer, Qt, QUrl
from PyQt6.QtGui import QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.decision_engine import DecisionEngine
from app.core.models import DashboardData, FlightState, Obstacle, Telemetry, parse_message
from app.network.ws_client import WebSocketClient


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Drone Dashboard")
        self.resize(1480, 900)

        self._queue: queue.Queue[dict] = queue.Queue()
        self._data = DashboardData()
        self._engine = DecisionEngine()
        self._last_state = FlightState.NORMAL

        self._client = WebSocketClient(
            on_message=self._on_raw_message,
            on_status=self._on_status,
        )

        self._battery_history: deque[float] = deque(maxlen=500)
        self._ultra_history: deque[float] = deque(maxlen=500)

        self._apply_theme()
        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(100)

        self._append_event("info", "Dashboard ready.")

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f5f1ea;
            }
            QWidget {
                color: #2a2825;
                font-family: "Segoe UI", "Trebuchet MS", sans-serif;
                font-size: 13px;
            }
            QLabel#ValueLabel {
                font-size: 14px;
                font-weight: 600;
                color: #24211f;
            }
            QLineEdit {
                background: #fffdf8;
                border: 1px solid #d7c7b0;
                border-radius: 8px;
                padding: 8px 10px;
                selection-background-color: #2f6e5e;
            }
            QLineEdit:focus {
                border: 1px solid #2f6e5e;
            }
            QPushButton {
                background: #2f6e5e;
                color: #ffffff;
                border: none;
                border-radius: 9px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #25584b;
            }
            QPushButton:pressed {
                background: #1f4a3f;
            }
            QPushButton#NeutralButton {
                background: #8f6d40;
            }
            QPushButton#NeutralButton:hover {
                background: #775a34;
            }
            QPushButton#DisconnectButton {
                background: #8f3c37;
            }
            QPushButton#DisconnectButton:hover {
                background: #742d2a;
            }
            QGroupBox {
                font-size: 14px;
                font-weight: 700;
                color: #3f3a35;
                border: 1px solid #ddcfba;
                border-radius: 12px;
                margin-top: 12px;
                background: #fffdf9;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QListWidget {
                border: 1px solid #dfd1bc;
                border-radius: 10px;
                background: #fffcf7;
                padding: 4px;
            }
            """
        )

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        top_bar = self._build_top_bar()
        content_grid = self._build_content_grid()

        layout.addLayout(top_bar)
        layout.addLayout(content_grid, 1)

    def _build_top_bar(self) -> QHBoxLayout:
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.status_label = QLabel("WS: disconnected")
        self.status_label.setStyleSheet("font-weight: 700; color: #4a443e;")
        self.ws_url_input = QLineEdit("ws://<drone-ip>:8765")
        self.state_label = QLabel("STATE: NORMAL")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_label.setMinimumWidth(180)

        self.connect_btn = QPushButton("Connect")
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setObjectName("DisconnectButton")

        self.connect_btn.clicked.connect(self._connect_ws)
        self.disconnect_btn.clicked.connect(self._disconnect_ws)

        top_bar.addWidget(self.status_label)
        top_bar.addWidget(self.ws_url_input, 1)
        top_bar.addWidget(self.connect_btn)
        top_bar.addWidget(self.disconnect_btn)
        top_bar.addWidget(self.state_label)
        return top_bar

    def _build_content_grid(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(12)

        telemetry_box = self._build_telemetry_box()
        plots_box = self._build_plots_box()
        right_col = self._build_right_column()

        grid.addWidget(telemetry_box, 0, 0)
        grid.addWidget(plots_box, 0, 1)
        grid.addWidget(right_col, 0, 2)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 3)
        return grid

    def _build_telemetry_box(self) -> QGroupBox:
        telemetry_box = QGroupBox("Telemetry")
        telemetry_layout = QFormLayout(telemetry_box)
        telemetry_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        telemetry_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        telemetry_layout.setHorizontalSpacing(14)
        telemetry_layout.setVerticalSpacing(10)

        self.battery_value = self._value_label("100.0 %")
        self.xyz_value = self._value_label("x=0.00 y=0.00 z=0.00 m")
        self.rpy_value = self._value_label("r=0.00 p=0.00 y=0.00 deg")
        self.vel_value = self._value_label("vx=0.00 vy=0.00 vz=0.00 m/s")
        self.mode_value = self._value_label("AUTO")
        self.ultra_value = self._value_label("999.0 cm")

        telemetry_layout.addRow("Battery", self.battery_value)
        telemetry_layout.addRow("Position", self.xyz_value)
        telemetry_layout.addRow("Attitude", self.rpy_value)
        telemetry_layout.addRow("Velocity", self.vel_value)
        telemetry_layout.addRow("Mode", self.mode_value)
        telemetry_layout.addRow("Ultrasonic", self.ultra_value)
        return telemetry_box

    def _build_plots_box(self) -> QGroupBox:
        plots_box = QGroupBox("Plots")
        plots_layout = QVBoxLayout(plots_box)
        plots_layout.setSpacing(10)

        self.battery_plot = self._create_plot("Battery %", (50, 132, 107), (0, 100))
        self.battery_curve = self.battery_plot.plot(pen=pg.mkPen(color=(50, 132, 107), width=2))

        self.ultra_plot = self._create_plot("Ultrasonic Distance (cm)", (180, 103, 53), (0, 250))
        self.ultra_curve = self.ultra_plot.plot(pen=pg.mkPen(color=(180, 103, 53), width=2))

        plots_layout.addWidget(self.battery_plot)
        plots_layout.addWidget(self.ultra_plot)
        return plots_box

    def _build_right_column(self) -> QWidget:
        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setSpacing(10)

        video_box = QGroupBox("Camera")
        video_layout = QVBoxLayout(video_box)
        self.video_url_input = QLineEdit("http://esp32-cam.local:81/stream")
        self.open_video_btn = QPushButton("Load Stream")
        self.open_video_btn.clicked.connect(self._load_video_stream)
        self.video_view = QWebEngineView()
        self.video_view.setMinimumHeight(260)
        video_layout.addWidget(self.video_url_input)
        video_layout.addWidget(self.open_video_btn)
        video_layout.addWidget(self.video_view)

        actions_box = QGroupBox("Action")
        actions_layout = QVBoxLayout(actions_box)
        self.action_text = QLabel("Normal operation.")
        self.action_text.setWordWrap(True)
        self.action_text.setFrameShape(QFrame.Shape.StyledPanel)
        self.action_text.setStyleSheet(
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
        actions_layout.addWidget(self.action_text)

        alerts_box = QGroupBox("Events")
        alerts_layout = QVBoxLayout(alerts_box)
        self.alert_list = QListWidget()
        alerts_layout.addWidget(self.alert_list)

        right_layout.addWidget(video_box)
        right_layout.addWidget(actions_box)
        right_layout.addWidget(alerts_box, 1)
        self._load_video_stream()
        return right_col

    def _value_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("ValueLabel")
        return label

    def _create_plot(self, title: str, line_color: tuple[int, int, int], y_range: tuple[int, int]) -> pg.PlotWidget:
        plot = pg.PlotWidget(title=title)
        plot.setYRange(*y_range)
        plot.showGrid(x=True, y=True, alpha=0.18)
        plot.setBackground("#fff9f2")
        axis_pen = pg.mkPen(color=line_color, width=1)
        plot.getAxis("left").setPen(axis_pen)
        plot.getAxis("bottom").setPen(axis_pen)
        return plot

    def _connect_ws(self) -> None:
        url = self.ws_url_input.text().strip()
        if not url:
            self._append_event("error", "WebSocket URL is empty.")
            return
        self._client.connect(url)

    def _disconnect_ws(self) -> None:
        self._client.disconnect()
        self.status_label.setText("WS: disconnected")
        self._append_event("info", "Disconnected from WebSocket.")

    def _on_raw_message(self, payload: dict) -> None:
        self._queue.put(payload)

    def _on_status(self, status: str) -> None:
        self._queue.put({"type": "_status", "status": status})

    def _tick(self) -> None:
        while True:
            try:
                payload = self._queue.get_nowait()
            except queue.Empty:
                break

            if payload.get("type") == "_status":
                self.status_label.setText(f"WS: {payload['status']}")
                continue

            parsed = parse_message(payload)
            if parsed is None:
                continue
            msg_type, item = parsed

            if msg_type == "telemetry":
                self._data.telemetry = item
            elif msg_type == "obstacle":
                self._data.obstacle = item
            elif msg_type == "event":
                self._append_event(item.level, item.text, item.timestamp)

        self._data.state = self._engine.evaluate(self._data.telemetry, self._data.obstacle)
        self._refresh_ui(self._data.telemetry, self._data.obstacle, self._data.state)

    def _refresh_ui(self, telemetry: Telemetry, obstacle: Obstacle, state: FlightState) -> None:
        self.battery_value.setText(f"{telemetry.battery_pct:.1f} %")
        self.xyz_value.setText(f"x={telemetry.x:.2f} y={telemetry.y:.2f} z={telemetry.z:.2f} m")
        self.rpy_value.setText(f"r={telemetry.roll:.2f} p={telemetry.pitch:.2f} y={telemetry.yaw:.2f} deg")
        self.vel_value.setText(f"vx={telemetry.vx:.2f} vy={telemetry.vy:.2f} vz={telemetry.vz:.2f} m/s")
        self.mode_value.setText(telemetry.mode)
        self.ultra_value.setText(f"{obstacle.ultrasonic_cm:.1f} cm ({obstacle.risk})")

        self._battery_history.append(telemetry.battery_pct)
        self._ultra_history.append(obstacle.ultrasonic_cm)
        self.battery_curve.setData(list(self._battery_history))
        self.ultra_curve.setData(list(self._ultra_history))

        self.state_label.setText(f"STATE: {state.value}")
        self.action_text.setText(self._engine.describe_action(state))
        self._paint_state(state)

        if state != self._last_state and state in {FlightState.SAFE_LAND, FlightState.EMERGENCY_DESCENT}:
            self._append_event("warn", self._engine.describe_action(state))
        self._last_state = state

    def _paint_state(self, state: FlightState) -> None:
        color = QColor("#2e7d32")
        if state == FlightState.AVOIDANCE:
            color = QColor("#ef6c00")
        elif state == FlightState.LOW_BAT_WARN:
            color = QColor("#f9a825")
        elif state == FlightState.SAFE_LAND:
            color = QColor("#c62828")
        elif state == FlightState.EMERGENCY_DESCENT:
            color = QColor("#6a1b9a")

        self.state_label.setStyleSheet(
            (
                "padding: 10px 12px; border-radius: 11px;"
                "font-weight: 800; color: white;"
                f"background-color: {color.name()};"
            )
        )

    def _append_event(self, level: str, text: str, ts: float | None = None) -> None:
        timestamp = dt.datetime.fromtimestamp(ts) if ts else dt.datetime.now()
        item = QListWidgetItem(f"[{timestamp.strftime('%H:%M:%S')}] {level.upper()} - {text}")
        if level.lower() in {"warn", "warning"}:
            item.setForeground(QColor("#ef6c00"))
        elif level.lower() in {"error", "critical"}:
            item.setForeground(QColor("#b71c1c"))

        self.alert_list.insertItem(0, item)
        if self.alert_list.count() > 200:
            self.alert_list.takeItem(self.alert_list.count() - 1)

    def _load_video_stream(self) -> None:
        url = self.video_url_input.text().strip()
        if url:
            self.video_view.setUrl(QUrl(url))
            self._append_event("info", f"Loaded video stream: {url}")

    def closeEvent(self, event) -> None:
        self._client.disconnect()
        super().closeEvent(event)
