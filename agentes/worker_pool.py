from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class WorkItem:
    correlation_id: str
    task_id: str
    subtask: str
    specialty: str | None
    context: str | None
    source_node: dict[str, Any]
    enqueued_at: datetime


class WorkerPool:
    def __init__(self, workers: int, max_queue: int = 128) -> None:
        self.workers = max(1, workers)
        self.queue: asyncio.Queue[tuple[WorkItem, asyncio.Future[str]]] = asyncio.Queue(maxsize=max_queue)
        self.active = 0
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self, handler) -> None:
        if self._tasks:
            return
        for idx in range(self.workers):
            self._tasks.append(asyncio.create_task(self._worker_loop(idx, handler)))

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def submit(self, item: WorkItem) -> asyncio.Future[str]:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[str] = loop.create_future()
        self.queue.put_nowait((item, fut))
        return fut

    def load_snapshot(self) -> dict[str, float | int]:
        queued = self.queue.qsize()
        total_capacity = self.workers + self.queue.maxsize
        current = self.active + queued
        utilization = (current / total_capacity) if total_capacity > 0 else 0.0
        return {
            "workers": self.workers,
            "active_tasks": self.active,
            "queue_size": queued,
            "queue_max": self.queue.maxsize,
            "utilization": round(utilization, 4),
            "available_slots": max(0, total_capacity - current),
        }

    async def _worker_loop(self, idx: int, handler) -> None:
        while True:
            item, fut = await self.queue.get()
            self.active += 1
            try:
                result = await handler(item)
                if not fut.done():
                    fut.set_result(result)
            except Exception as exc:  # pragma: no cover
                if not fut.done():
                    fut.set_exception(exc)
            finally:
                self.active = max(0, self.active - 1)
                self.queue.task_done()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
