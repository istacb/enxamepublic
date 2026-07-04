from __future__ import annotations

import time
from collections import deque

try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None


class MetricsCollector:
    def __init__(self, max_samples: int = 200) -> None:
        self._latencies_ms: deque[float] = deque(maxlen=max_samples)
        self._completed = 0
        self._failed = 0
        self._started_at = time.monotonic()

    def track_latency(self, value_ms: float) -> None:
        self._latencies_ms.append(max(0.0, value_ms))

    def track_success(self) -> None:
        self._completed += 1

    def track_failure(self) -> None:
        self._failed += 1

    def snapshot(self) -> dict:
        elapsed = max(1e-6, time.monotonic() - self._started_at)
        avg_ms = sum(self._latencies_ms) / len(self._latencies_ms) if self._latencies_ms else 0.0
        p95_ms = 0.0
        if self._latencies_ms:
            values = sorted(self._latencies_ms)
            idx = min(len(values) - 1, int(len(values) * 0.95))
            p95_ms = values[idx]

        cpu = 0.0
        ram = 0.0
        if psutil is not None:
            cpu = float(psutil.cpu_percent(interval=None))
            ram = float(psutil.virtual_memory().percent)

        return {
            "cpu_percent": round(cpu, 2),
            "ram_percent": round(ram, 2),
            "avg_latency_ms": round(avg_ms, 2),
            "p95_latency_ms": round(p95_ms, 2),
            "tasks_completed": self._completed,
            "tasks_failed": self._failed,
            "throughput_tps": round((self._completed + self._failed) / elapsed, 3),
        }
