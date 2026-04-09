from __future__ import annotations

import queue

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.decision_engine import DecisionEngine
from app.core.models import DashboardData, FlightState, VisionObstacle, parse_message
from app.gui.panels import ActionPanel, CameraPanel, EventsPanel, PlotsPanel, TelemetryPanel
from app.gui.theme import get_main_stylesheet
from app.network.ws_client import WebSocketClient
from app.vision.yolo_detector import VisionDetectionResult, YoloStreamDetector


RIGHT_PANEL_WIDTH = 480


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Drone Dashboard")
        self.resize(1480, 900)

        self._queue: queue.Queue[dict] = queue.Queue()
        self._data = DashboardData()
        self._engine = DecisionEngine()
        self._last_state = FlightState.NORMAL

        self._vision_detector = YoloStreamDetector(
            on_detection=self._on_vision_detection,
            on_status=self._on_vision_status,
        )
        self._client = WebSocketClient(
            on_message=self._on_raw_message,
            on_status=self._on_status,
        )

        self.setStyleSheet(get_main_stylesheet())
        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(100)

        self._append_event("info", "Dashboard ready.")

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        layout.addLayout(self._build_top_bar())
        layout.addLayout(self._build_content_grid(), 1)

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

        self.telemetry_panel = TelemetryPanel()
        self.plots_panel = PlotsPanel()
        self.camera_panel = CameraPanel(
            on_start=self._start_vision_detection,
            on_stop=self._stop_vision_detection,
        )
        self.action_panel = ActionPanel()
        self.events_panel = EventsPanel()

        right_col = QWidget()
        right_col.setMinimumWidth(RIGHT_PANEL_WIDTH)
        right_col.setMaximumWidth(RIGHT_PANEL_WIDTH)
        right_layout = QVBoxLayout(right_col)
        right_layout.setSpacing(10)
        right_layout.addWidget(self.camera_panel)
        right_layout.addWidget(self.action_panel)
        right_layout.addWidget(self.events_panel, 1)

        grid.addWidget(self.telemetry_panel, 0, 0)
        grid.addWidget(self.plots_panel, 0, 1)
        grid.addWidget(right_col, 0, 2)

        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 0)
        grid.setColumnMinimumWidth(2, RIGHT_PANEL_WIDTH)
        return grid

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

    def _on_vision_status(self, status: str) -> None:
        self._queue.put({"type": "_vision_status", "status": status})

    def _tick(self) -> None:
        telemetry_updated = False
        obstacle_updated = False

        while True:
            try:
                payload = self._queue.get_nowait()
            except queue.Empty:
                break

            payload_type = payload.get("type")
            if payload_type == "_status":
                self.status_label.setText(f"WS: {payload['status']}")
                continue

            if payload_type == "_vision_status":
                self.camera_panel.set_status(payload["status"])
                continue

            if payload_type == "_vision":
                data = payload.get("data", {})
                self._data.vision = VisionObstacle(
                    detected=bool(data.get("detected", False)),
                    confidence=float(data.get("confidence", 0.0)),
                    label=str(data.get("label", "none")),
                    count=int(data.get("count", 0)),
                    timestamp=float(data.get("timestamp", 0.0)),
                )

                frame_jpeg = data.get("frame_jpeg")
                if isinstance(frame_jpeg, bytes):
                    self.camera_panel.set_preview(frame_jpeg)
                continue

            parsed = parse_message(payload)
            if parsed is None:
                continue

            msg_type, item = parsed
            if msg_type == "telemetry":
                self._data.telemetry = item
                telemetry_updated = True
            elif msg_type == "obstacle":
                self._data.obstacle = item
                obstacle_updated = True
            elif msg_type == "vision_obstacle":
                self._data.vision = item
            elif msg_type == "event":
                self._append_event(item.level, item.text, item.timestamp)

        self._refresh_ui(telemetry_updated, obstacle_updated)

    def _refresh_ui(self, telemetry_updated: bool, obstacle_updated: bool) -> None:
        self._data.state = self._engine.evaluate(self._data.telemetry, self._data.obstacle, self._data.vision)

        self.telemetry_panel.update_values(self._data.telemetry, self._data.obstacle, self._data.vision)

        if telemetry_updated:
            self.plots_panel.push_battery(self._data.telemetry.battery_pct)
        if obstacle_updated:
            self.plots_panel.push_ultrasonic(self._data.obstacle.ultrasonic_cm)

        self.state_label.setText(f"STATE: {self._data.state.value}")
        self._paint_state(self._data.state)

        action_text = self._engine.describe_action(self._data.state)
        if self._data.state == FlightState.AVOIDANCE and self._data.vision.detected:
            action_text = "Obstacle detected by camera. Apply path correction and limit forward velocity."
        self.action_panel.set_action(action_text)

        if self._data.state != self._last_state and self._data.state in {
            FlightState.SAFE_LAND,
            FlightState.EMERGENCY_DESCENT,
        }:
            self._append_event("warn", self._engine.describe_action(self._data.state))

        self._last_state = self._data.state

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

    def _start_vision_detection(self) -> None:
        source = self.camera_panel.source_text() or "auto"
        self._vision_detector.start(
            stream_url=source,
            model_path="yolov8n.pt",
            confidence_threshold=0.5,
            infer_fps=4.0,
        )
        self._append_event("info", f"Vision detector started on source: {source}")

    def _stop_vision_detection(self) -> None:
        self._vision_detector.stop()
        self._append_event("info", "Vision detector stopped.")

    def _on_vision_detection(self, result: VisionDetectionResult) -> None:
        self._queue.put(
            {
                "type": "_vision",
                "data": {
                    "detected": result.detected,
                    "confidence": result.confidence,
                    "label": result.label,
                    "count": result.count,
                    "timestamp": result.timestamp,
                    "frame_jpeg": result.frame_jpeg,
                },
            }
        )

    def _append_event(self, level: str, text: str, ts: float | None = None) -> None:
        self.events_panel.append_event(level, text, ts)

    def closeEvent(self, event) -> None:
        self._vision_detector.stop()
        self._client.disconnect()
        super().closeEvent(event)
