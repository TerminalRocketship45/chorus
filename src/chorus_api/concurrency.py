"""Serialises calls to the (CPU, single-process) analysis pipeline.

Only one `chorus.pipeline.analyze` call may run at a time (it is not
thread-safe to run concurrently against a shared CPU budget on the login
node), with a small wait queue: once more than `max_queue` requests are
already waiting their turn, a new request is rejected immediately with
`AnalysisBusy` rather than piling up indefinitely.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class AnalysisBusy(Exception):
    """Raised instead of queuing when the wait queue is already full."""


class AnalysisGate:
    def __init__(self, max_queue: int = 3) -> None:
        self._sem = asyncio.Semaphore(1)
        self._max_queue = max_queue
        self._waiting = 0
        self._lock = asyncio.Lock()

    async def run(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Run `func(*args, **kwargs)` in a worker thread, queued behind any
        analysis already running. Raises AnalysisBusy without blocking if the
        queue (requests already waiting, not counting the one running) is
        already at `max_queue`.
        """
        async with self._lock:
            if self._waiting >= self._max_queue:
                raise AnalysisBusy(
                    f"analyzer is busy ({self._max_queue} requests already waiting)"
                )
            self._waiting += 1

        decremented = False
        try:
            async with self._sem:
                async with self._lock:
                    self._waiting -= 1
                decremented = True
                return await asyncio.to_thread(func, *args, **kwargs)
        finally:
            if not decremented:
                async with self._lock:
                    self._waiting -= 1
