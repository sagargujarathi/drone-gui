from __future__ import annotations

import asyncio
import json
import threading
from typing import Callable

import websockets


class WebSocketClient:
    def __init__(self, on_message: Callable[[dict], None], on_status: Callable[[str], None]) -> None:
        self._url = ""
        self._on_message = on_message
        self._on_status = on_status
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def connect(self, url: str) -> None:
        self.disconnect()
        self._url = url
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def disconnect(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        asyncio.run(self._consume())

    async def _consume(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._on_status("connecting")
                async with websockets.connect(self._url, ping_interval=10, ping_timeout=10) as ws:
                    self._on_status("connected")
                    while not self._stop_event.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        payload = json.loads(raw)
                        self._on_message(payload)
            except TimeoutError:
                continue
            except Exception as exc:  # Keep trying until stopped.
                self._on_status(f"disconnected: {exc}")
                await asyncio.sleep(1.0)
