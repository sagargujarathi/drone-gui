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

## Message Envelope

All messages follow:

```json
{
  "type": "telemetry | obstacle | event | heartbeat",
  "ts": 1710000000.12,
  "source": "pi",
  "data": {}
}
```

## Hardware Integration Notes

- Keep the same message contract from hardware-side publishers.
- ESP32-CAM stream is displayed directly inside the GUI Camera panel.
