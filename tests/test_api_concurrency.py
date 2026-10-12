"""Direct tests of the analysis gate's serialize-to-one / wait-queue-of-N logic
(POST /api/analyze: "serialised with a lock/semaphore of 1, with a small wait
queue"). Exercised directly with asyncio.run (no pytest-asyncio dependency)
rather than through real concurrent HTTP requests, which TestClient cannot
reliably produce.
"""
import asyncio
import time

import pytest

from chorus_api.concurrency import AnalysisBusy, AnalysisGate


def _slow(x, delay=0.05):
    time.sleep(delay)
    return x


def test_runs_sequentially_and_returns_results_in_order():
    async def main():
        gate = AnalysisGate(max_queue=3)
        return await asyncio.gather(*(gate.run(_slow, i, 0.02) for i in range(4)))

    assert asyncio.run(main()) == [0, 1, 2, 3]


def test_rejects_once_the_wait_queue_is_full():
    async def main():
        gate = AnalysisGate(max_queue=2)

        # One long-running task occupies the single "running" slot.
        running = asyncio.create_task(gate.run(_slow, "running", 0.2))
        await asyncio.sleep(0.02)  # let it acquire the semaphore

        # Two more fill the wait queue (max_queue=2).
        waiter1 = asyncio.create_task(gate.run(_slow, "w1", 0.05))
        waiter2 = asyncio.create_task(gate.run(_slow, "w2", 0.05))
        await asyncio.sleep(0.02)  # let them register as waiting

        # A fourth concurrent request must be rejected immediately.
        with pytest.raises(AnalysisBusy):
            await gate.run(_slow, "rejected", 0.01)

        assert await running == "running"
        assert await waiter1 == "w1"
        assert await waiter2 == "w2"

    asyncio.run(main())


def test_queue_slot_frees_up_after_a_request_finishes():
    async def main():
        gate = AnalysisGate(max_queue=1)

        running = asyncio.create_task(gate.run(_slow, "running", 0.1))
        await asyncio.sleep(0.02)
        waiter = asyncio.create_task(gate.run(_slow, "waiter", 0.02))
        await asyncio.sleep(0.02)

        # Queue (max_queue=1) is now full; a second waiter must be rejected.
        with pytest.raises(AnalysisBusy):
            await gate.run(_slow, "rejected", 0.01)

        assert await running == "running"
        assert await waiter == "waiter"

        # Now that both are done, a fresh request should succeed immediately.
        assert await gate.run(_slow, "fresh", 0.01) == "fresh"

    asyncio.run(main())


def test_exception_in_func_propagates_and_releases_the_slot():
    async def main():
        gate = AnalysisGate(max_queue=1)

        def boom():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await gate.run(boom)

        # The gate must not be left locked/occupied after an error.
        assert await gate.run(_slow, "ok", 0.01) == "ok"

    asyncio.run(main())
