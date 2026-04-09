from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class VisionDetectionResult:
    detected: bool
    confidence: float
    label: str
    count: int
    timestamp: float
    frame_jpeg: bytes | None = None


class YoloStreamDetector:
    def __init__(
        self,
        on_detection: Callable[[VisionDetectionResult], None],
        on_status: Callable[[str], None],
    ) -> None:
        self._on_detection = on_detection
        self._on_status = on_status
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(
        self,
        stream_url: str,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = 0.35,
        infer_fps: float = 4.0,
    ) -> None:
        self.stop()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            kwargs={
                "stream_url": stream_url,
                "model_path": model_path,
                "confidence_threshold": confidence_threshold,
                "infer_fps": infer_fps,
            },
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _emit_status(self, text: str) -> None:
        self._on_status(text)

    def _run(
        self,
        stream_url: str,
        model_path: str,
        confidence_threshold: float,
        infer_fps: float,
    ) -> None:
        try:
            import cv2
        except Exception as exc:
            self._emit_status(f"error: OpenCV not available ({exc})")
            return

        try:
            from ultralytics import YOLO
        except Exception as exc:
            self._emit_status(f"error: ultralytics not available ({exc})")
            return

        try:
            model = YOLO(model_path)
            self._emit_status(f"model loaded: {model_path}")
        except Exception as exc:
            self._emit_status(f"error: failed to load model ({exc})")
            return

        source = self._parse_capture_source(stream_url)
        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            self._emit_status("error: cannot open stream")
            return

        # Keep camera buffer shallow to reduce UI lag.
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self._emit_status(f"running ({source})")
        infer_period = 1.0 / max(infer_fps, 1.0)
        preview_period = 1.0 / 10.0
        last_infer_ts = 0.0
        last_preview_ts = 0.0
        read_failures = 0
        last_detection = VisionDetectionResult(
            detected=False,
            confidence=0.0,
            label="none",
            count=0,
            timestamp=time.time(),
            frame_jpeg=None,
        )

        while not self._stop_event.is_set():
            ok, frame = capture.read()
            if not ok:
                read_failures += 1
                if read_failures >= 20:
                    capture.release()
                    capture = cv2.VideoCapture(source)
                    read_failures = 0
                time.sleep(0.05)
                continue

            read_failures = 0
            now = time.time()
            if now - last_infer_ts >= infer_period:
                last_infer_ts = now
                try:
                    results = model.predict(frame, conf=confidence_threshold, imgsz=640, verbose=False)
                    result = results[0]
                    filtered = self._filter_detections(result, frame.shape)

                    if not filtered:
                        last_detection = VisionDetectionResult(
                            detected=False,
                            confidence=0.0,
                            label="none",
                            count=0,
                            timestamp=now,
                            frame_jpeg=self._encode_frame(frame, cv2),
                        )
                    else:
                        best = max(filtered, key=lambda d: d["confidence"])
                        annotated = self._draw_filtered_boxes(frame, filtered, cv2)
                        last_detection = VisionDetectionResult(
                            detected=True,
                            confidence=float(best["confidence"]),
                            label=str(best["label"]),
                            count=len(filtered),
                            timestamp=now,
                            frame_jpeg=self._encode_frame(annotated, cv2),
                        )
                except Exception as exc:
                    self._emit_status(f"inference error: {exc}")
                    time.sleep(0.1)

            if now - last_preview_ts >= preview_period:
                last_preview_ts = now
                if last_detection.frame_jpeg is None:
                    last_detection = VisionDetectionResult(
                        detected=last_detection.detected,
                        confidence=last_detection.confidence,
                        label=last_detection.label,
                        count=last_detection.count,
                        timestamp=now,
                        frame_jpeg=self._encode_frame(frame, cv2),
                    )
                self._on_detection(last_detection)

        capture.release()
        self._emit_status("stopped")

    def _filter_detections(self, result, frame_shape: tuple[int, int, int]) -> list[dict[str, float | str | tuple[int, int, int, int]]]:
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []

        names = result.names if hasattr(result, "names") else {}
        frame_h, frame_w = frame_shape[0], frame_shape[1]
        frame_area = max(1.0, float(frame_h * frame_w))
        min_area_ratio = 0.012
        ignored_labels = {"frisbee", "sports ball", "clock"}

        confs = boxes.conf.tolist()
        classes = boxes.cls.tolist()
        coords = boxes.xyxy.tolist()

        filtered: list[dict[str, float | str | tuple[int, int, int, int]]] = []
        for idx, conf in enumerate(confs):
            cls_id = int(classes[idx]) if idx < len(classes) else -1
            if isinstance(names, dict):
                label = str(names.get(cls_id, cls_id))
            else:
                label = str(cls_id)

            label_lower = label.lower()
            if label_lower in ignored_labels or "spinner" in label_lower:
                continue

            x1, y1, x2, y2 = coords[idx]
            box_w = max(0.0, float(x2 - x1))
            box_h = max(0.0, float(y2 - y1))
            box_area_ratio = (box_w * box_h) / frame_area
            if box_area_ratio < min_area_ratio:
                continue

            filtered.append(
                {
                    "label": label,
                    "confidence": float(conf),
                    "xyxy": (int(x1), int(y1), int(x2), int(y2)),
                }
            )

        return filtered

    def _draw_filtered_boxes(self, frame, detections: list[dict[str, float | str | tuple[int, int, int, int]]], cv2):
        annotated = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det["xyxy"]
            label = str(det["label"])
            conf = float(det["confidence"])
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (46, 125, 50), 2)
            cv2.putText(
                annotated,
                f"{label} {conf:.2f}",
                (x1, max(12, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (46, 125, 50),
                2,
                cv2.LINE_AA,
            )
        return annotated

    def _parse_capture_source(self, stream_url: str) -> str | int:
        raw = stream_url.strip()
        lower = raw.lower()

        if lower in {"", "auto", "camera", "cam", "webcam", "webcam:auto"}:
            idx = self._find_first_camera_index()
            return idx if idx is not None else 0

        if lower.startswith("webcam"):
            if ":" in raw:
                _, idx_raw = raw.split(":", 1)
                idx_raw = idx_raw.strip()
                if idx_raw.isdigit():
                    return int(idx_raw)
            return 0

        if raw.isdigit():
            return int(raw)

        return raw

    def _find_first_camera_index(self, max_index: int = 5) -> int | None:
        try:
            import cv2
        except Exception:
            return None

        for idx in range(max_index + 1):
            cap = cv2.VideoCapture(idx)
            ok = cap.isOpened()
            if ok:
                read_ok, _ = cap.read()
                cap.release()
                if read_ok:
                    return idx
            else:
                cap.release()
        return None

    def _encode_frame(self, frame, cv2) -> bytes | None:
        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            return None
        return encoded.tobytes()
