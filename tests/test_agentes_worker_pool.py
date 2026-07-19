from __future__ import annotations

import asyncio

from agentes.worker_pool import WorkItem, WorkerPool, now_utc


def test_worker_pool_executes_item() -> None:
    async def runner() -> None:
        pool = WorkerPool(workers=1, max_queue=10)

        async def handler(item: WorkItem) -> str:
            await asyncio.sleep(0.01)
            return f"ok:{item.subtask}"

        await pool.start(handler)
        item = WorkItem(
            correlation_id="c1",
            task_id="t1",
            subtask="teste",
            specialty="programador",
            context=None,
            source_node={"node_id": "juiz-01", "role": "juiz"},
            enqueued_at=now_utc(),
        )

        fut = await pool.submit(item)
        result = await asyncio.wait_for(fut, timeout=1)
        assert result == "ok:teste"

        load = pool.load_snapshot()
        assert load["workers"] == 1

        await pool.stop()

    asyncio.run(runner())
