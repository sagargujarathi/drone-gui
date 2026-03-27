from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FlightState(str, Enum):
    NORMAL = "NORMAL"
    AVOIDANCE = "AVOIDANCE"
    LOW_BAT_WARN = "LOW_BAT_WARN"
    SAFE_LAND = "SAFE_LAND"
    EMERGENCY_DESCENT = "EMERGENCY_DESCENT"


@dataclass
class Telemetry:
    battery_pct: float = 100.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    mode: str = "AUTO"
    timestamp: float = 0.0


@dataclass
class Obstacle:
    ultrasonic_cm: float = 999.0
    sector: str = "front"
    risk: str = "low"
    timestamp: float = 0.0


@dataclass
class EventMessage:
    level: str
    text: str
    timestamp: float
    source: str = "system"


@dataclass
class DashboardData:
    telemetry: Telemetry = field(default_factory=Telemetry)
    obstacle: Obstacle = field(default_factory=Obstacle)
    state: FlightState = FlightState.NORMAL


def parse_message(payload: dict[str, Any]) -> tuple[str, Any] | None:
    msg_type = payload.get("type")
    ts = float(payload.get("ts", 0.0))
    data = payload.get("data", {})

    if msg_type == "telemetry":
        xyz = data.get("xyz_m", {})
        rpy = data.get("rpy_deg", {})
        vel = data.get("vel_mps", {})
        item = Telemetry(
            battery_pct=float(data.get("battery_pct", 0.0)),
            x=float(xyz.get("x", 0.0)),
            y=float(xyz.get("y", 0.0)),
            z=float(xyz.get("z", 0.0)),
            roll=float(rpy.get("roll", 0.0)),
            pitch=float(rpy.get("pitch", 0.0)),
            yaw=float(rpy.get("yaw", 0.0)),
            vx=float(vel.get("vx", 0.0)),
            vy=float(vel.get("vy", 0.0)),
            vz=float(vel.get("vz", 0.0)),
            mode=str(data.get("mode", "AUTO")),
            timestamp=ts,
        )
        return msg_type, item

    if msg_type == "obstacle":
        item = Obstacle(
            ultrasonic_cm=float(data.get("ultrasonic_cm", 999.0)),
            sector=str(data.get("sector", "front")),
            risk=str(data.get("risk", "low")),
            timestamp=ts,
        )
        return msg_type, item

    if msg_type == "event":
        item = EventMessage(
            level=str(data.get("level", "info")),
            text=str(data.get("text", "")),
            timestamp=ts,
            source=str(payload.get("source", "system")),
        )
        return msg_type, item

    return None
