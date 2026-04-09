from __future__ import annotations

from dataclasses import dataclass

from app.core.models import FlightState, Obstacle, Telemetry, VisionObstacle


@dataclass
class SafetyThresholds:
    obstacle_avoid_cm: float = 80.0
    vision_confidence_min: float = 0.35
    low_battery_warn_pct: float = 30.0
    safe_land_pct: float = 20.0
    emergency_descent_pct: float = 12.0


class DecisionEngine:
    def __init__(self, thresholds: SafetyThresholds | None = None) -> None:
        self.thresholds = thresholds or SafetyThresholds()

    def evaluate(self, telemetry: Telemetry, obstacle: Obstacle, vision: VisionObstacle | None = None) -> FlightState:
        battery = telemetry.battery_pct
        distance = obstacle.ultrasonic_cm
        has_vision_obstacle = False
        if vision is not None:
            has_vision_obstacle = vision.detected and vision.confidence >= self.thresholds.vision_confidence_min

        if battery <= self.thresholds.emergency_descent_pct:
            return FlightState.EMERGENCY_DESCENT

        if battery <= self.thresholds.safe_land_pct:
            return FlightState.SAFE_LAND

        if distance <= self.thresholds.obstacle_avoid_cm or has_vision_obstacle:
            return FlightState.AVOIDANCE

        if battery <= self.thresholds.low_battery_warn_pct:
            return FlightState.LOW_BAT_WARN

        return FlightState.NORMAL

    def describe_action(self, state: FlightState) -> str:
        if state == FlightState.EMERGENCY_DESCENT:
            return "Emergency descent active: reduce thrust and descend immediately."
        if state == FlightState.SAFE_LAND:
            return "Safe landing requested: navigate to safe zone and land."
        if state == FlightState.AVOIDANCE:
            return "Obstacle detected: apply path correction and limit forward velocity."
        if state == FlightState.LOW_BAT_WARN:
            return "Low battery warning: prepare return-to-home or landing."
        return "Normal operation."
