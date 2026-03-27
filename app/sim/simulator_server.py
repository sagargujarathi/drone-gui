from __future__ import annotations

import asyncio
import json
import math
import random
import threading
import time
from dataclasses import dataclass

import websockets


@dataclass
class SimState:
    battery_pct: float = 100.0
    x: float = 0.0
    y: float = 0.0
    z: float = 2.0
    yaw: float = 0.0
    t: float = 0.0


class SimulatorServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._clients: set[websockets.WebSocketServerProtocol] = set()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._state = SimState()

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.create_task(self._serve())
        self._loop.create_task(self._broadcast_loop())
        self._loop.run_forever()

    async def _serve(self) -> None:
        async def handler(ws: websockets.WebSocketServerProtocol) -> None:
            self._clients.add(ws)
            try:
                await ws.wait_closed()
            finally:
                self._clients.discard(ws)

        await websockets.serve(handler, self.host, self.port)

    async def _broadcast_loop(self) -> None:
        while not self._stop_event.is_set():
            self._state.t += 0.1
            self._state.battery_pct = max(0.0, self._state.battery_pct - 0.02)
            self._state.x = math.sin(self._state.t * 0.5) * 4.0
            self._state.y = math.cos(self._state.t * 0.4) * 3.0
            self._state.z = 2.0 + 0.6 * math.sin(self._state.t * 0.7)
            self._state.yaw = (self._state.yaw + 1.2) % 360.0

            now = time.time()
            roll = 8.0 * math.sin(self._state.t)
            pitch = 6.0 * math.cos(self._state.t * 0.8)
            ultrasonic = 40.0 + 120.0 * abs(math.sin(self._state.t * 0.55)) + random.uniform(-3.0, 3.0)
            risk = "high" if ultrasonic < 60 else "medium" if ultrasonic < 100 else "low"

            telemetry = {
                "type": "telemetry",
                "ts": now,
                "source": "pi",
                "data": {
                    "battery_pct": round(self._state.battery_pct, 2),
                    "xyz_m": {"x": round(self._state.x, 2), "y": round(self._state.y, 2), "z": round(self._state.z, 2)},
                    "rpy_deg": {"roll": round(roll, 2), "pitch": round(pitch, 2), "yaw": round(self._state.yaw, 2)},
                    "vel_mps": {
                        "vx": round(0.2 * math.cos(self._state.t * 0.5), 3),
                        "vy": round(-0.16 * math.sin(self._state.t * 0.4), 3),
                        "vz": round(0.42 * math.cos(self._state.t * 0.7), 3),
                    },
                    "mode": "AUTO",
                },
            }

            obstacle = {
                "type": "obstacle",
                "ts": now,
                "source": "pi",
                "data": {
                    "ultrasonic_cm": round(max(15.0, ultrasonic), 2),
                    "sector": "front",
                    "risk": risk,
                },
            }

            await self._broadcast(telemetry)
            await self._broadcast(obstacle)
            await asyncio.sleep(0.1)

    async def _broadcast(self, payload: dict) -> None:
        if not self._clients:
            return

        encoded = json.dumps(payload)
        dead: list[websockets.WebSocketServerProtocol] = []
        for client in list(self._clients):
            try:
                await client.send(encoded)
            except Exception:
                dead.append(client)

        for client in dead:
            self._clients.discard(client)
