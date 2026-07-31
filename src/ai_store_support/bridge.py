from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from concurrent.futures import Future
from threading import Event, RLock, Thread
from typing import Any, Protocol

from .runtime_status import RuntimeStatusRegistry


class AsyncChannelRunner(Protocol):
    async def run(self) -> None: ...
    async def stop(self) -> None: ...


class BridgeSupervisor:
    """Runs authorized channel adapters on one background asyncio loop."""

    def __init__(self, registry: RuntimeStatusRegistry | None = None):
        self.registry = registry or RuntimeStatusRegistry()
        self._lock = RLock()
        self._ready = Event()
        self._thread: Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._runners: dict[str, AsyncChannelRunner] = {}
        self._futures: dict[str, Future[Any]] = {}

    def start_runner(self, *, runtime_key: str, shop_key: str, channel: str, account_key: str, runner: AsyncChannelRunner, display_name: str = "") -> None:
        self._ensure_loop()
        with self._lock:
            existing = self._futures.get(runtime_key)
            if existing and not existing.done():
                raise RuntimeError(f"渠道账号已在运行: {runtime_key}")
            self.registry.register(runtime_key, shop_key=shop_key, channel=channel, account_key=account_key, display_name=display_name)
            self.registry.set_state(runtime_key, "starting")
            self._runners[runtime_key] = runner
            future = asyncio.run_coroutine_threadsafe(self._run(runtime_key, runner), self._required_loop())
            self._futures[runtime_key] = future

    def stop_runner(self, runtime_key: str, timeout: float = 10.0) -> None:
        with self._lock:
            runner = self._runners.get(runtime_key)
            future = self._futures.get(runtime_key)
        if runner is None:
            return
        self.registry.set_state(runtime_key, "stopping")
        stop_future = asyncio.run_coroutine_threadsafe(runner.stop(), self._required_loop())
        stop_future.result(timeout=timeout)
        if future:
            try:
                future.result(timeout=timeout)
            except Exception:
                pass
        with self._lock:
            self._runners.pop(runtime_key, None)
            self._futures.pop(runtime_key, None)
        self.registry.set_state(runtime_key, "disconnected")

    def stop_all(self, timeout: float = 10.0) -> None:
        with self._lock:
            keys = list(self._runners)
        for runtime_key in keys:
            try:
                self.stop_runner(runtime_key, timeout=timeout)
            except Exception as exc:
                try:
                    self.registry.set_state(runtime_key, "error", error=str(exc))
                except KeyError:
                    pass
        loop = self._loop
        if loop and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        self._loop = None
        self._thread = None
        self._ready.clear()

    def submit(self, coroutine: Coroutine[Any, Any, Any]) -> Future[Any]:
        self._ensure_loop()
        return asyncio.run_coroutine_threadsafe(coroutine, self._required_loop())

    async def _run(self, runtime_key: str, runner: AsyncChannelRunner) -> None:
        self.registry.set_state(runtime_key, "connecting")
        try:
            self.registry.set_state(runtime_key, "connected")
            await runner.run()
            self.registry.set_state(runtime_key, "disconnected")
        except asyncio.CancelledError:
            self.registry.set_state(runtime_key, "disconnected")
            raise
        except Exception as exc:
            self.registry.set_state(runtime_key, "error", error=str(exc))
            raise

    def _ensure_loop(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive() and self._loop and self._loop.is_running():
                return
            self._ready.clear()
            self._thread = Thread(target=self._loop_worker, name="ai-store-support-bridge", daemon=True)
            self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise RuntimeError("渠道桥接事件循环启动失败")

    def _loop_worker(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    def _required_loop(self) -> asyncio.AbstractEventLoop:
        loop = self._loop
        if loop is None or not loop.is_running():
            raise RuntimeError("渠道桥接事件循环未运行")
        return loop
