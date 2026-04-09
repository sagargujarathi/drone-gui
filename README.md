# Drone Desktop GUI

Desktop GUI for drone telemetry monitoring with WebSocket transport.

Built with PyQt6 and pyqtgraph.

## Features

- Real-time telemetry display (battery, XYZ, roll/pitch/yaw)
- Live plots for battery and ultrasonic distance
- Safety decision engine states:
  - `NORMAL`
  - `AVOIDANCE`
  - `LOW_BAT_WARN`
  - `SAFE_LAND`
  - `EMERGENCY_DESCENT`
- In-app camera stream panel (ESP32-CAM URL)
- Optional YOLO-based camera obstacle detection from ESP32-CAM stream
- Alerts/event timeline panel

## Project Structure

- `app/main.py` - App entry point
- `app/gui/main_window.py` - Main dashboard window
- `app/network/ws_client.py` - WebSocket client thread
- `app/core/decision_engine.py` - Safety state machine
- `app/core/models.py` - Data models

## Quick Start

1. Create a Python environment and install dependencies.
2. Run:

```bash
python -m app.main
```

Alternative (also supported):

```bash
cd app
python main.py
```

Set your real drone WebSocket URL in the top bar and click **Connect**.

## ESP32-CAM + YOLO Flow

Use this when you want camera detections to influence `AVOIDANCE` state in addition to ultrasonic input.

1. Connect laptop to the ESP32-CAM WiFi AP (or same network where camera is reachable).
2. In the GUI Camera panel:
  - Set source to `auto` for laptop camera auto-detection
  - Or set source to `webcam:0` / `0` / your ESP32 HTTP stream URL
3. Click **Start Camera Detection**.
4. Watch live annotated preview in the Camera panel.

When YOLO detects an object above threshold, dashboard state can transition to `AVOIDANCE` even if ultrasonic risk is low.

## Message Envelope

All messages follow:

```json
{
  "type": "telemetry | obstacle | vision_obstacle | event | heartbeat",
  "ts": 1710000000.12,
  "source": "pi",
  "data": {}
}
```

## Hardware Integration Notes

- Keep the same message contract from hardware-side publishers.
- YOLO detection runs locally on the laptop from the selected camera source.
