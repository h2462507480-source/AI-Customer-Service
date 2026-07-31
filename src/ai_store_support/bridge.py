from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from threading import Event, RLock, Thread
from typing import Any, Protocol

from .operation_log import OperationLog
from .runtime_status import RuntimeStatusRegistry


class AsyncChannelRunner(Protocol):
    async def run(self) -> None: ...
    async def stop(self) -> None: ...


@dataclass(frozen=True)
class RestartPolicy:
    max_restarts: int = 8
    initial_delay: float = 1.0
    max_delay: float = 60.0
    multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.max_restarts < 0:
            raise ValueError("max_restarts cannot be negative")
        if self.initial_delay < 0 or self.max_delay < 0 or self.multiplier < 1:
            raise ValueError("invalid restart backoff settings")


class BridgeSupervisor:
    """Runs channel adapters on a background loop and restarts guarded runners after crashes."""

    def __init__(
        self,
        registry: RuntimeStatusRegistry | None = None,
        operation_log: OperationLog | None = None,
    ):
        self.registry = registry or RuntimeStatusRegistry()
        self.operation_log = operation_log
        self._lock = RLock()
        self._ready = Event()
        self._thread: Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._runners: dict[str, AsyncChannelRunner] = {}
        self._futures: dict[str, Future[Any]] = {}
        self._stop_requested: set[str] = set()

    def start_runner(
        self,
        *,
        runtime_key: str,
        shop_key: str,
        channel: str,
        account_key: str,
        runner: AsyncChannelRunner,
        display_name: str = "",
    ) -> None:
        """Start one non-restarting runner. Use start_guarded_runner for automatic recovery."""

        self.start_guarded_runner(
            runtime_key=runtime_key,
            shop_key=shop_key,
            channel=channel,
            account_key=account_key,
            runner_factory=lambda: runner,
            display_name=display_name,
            restart_policy=RestartPolicy(max_restarts=0),
        )

    def start_guarded_runner(
        self,
        *,
        runtime_key: str,
        shop_key: str,
        channel: str,
        account_key: str,
        runner_factory: Callable[[], AsyncChannelRunner],
        display_name: str = "",
        restart_policy: RestartPolicy | None = None,
    ) -> None:
        self._ensure_loop()
        with self._lock:
            existing = self._futures.get(runtime_key)
            if existing and not existing.done():
                raise RuntimeError(f"渠道账号已在运行: {runtime_key}")
            self.registry.register(
                runtime_key,
                shop_key=shop_key,
                channel=channel,
                account_key=account_key,
                display_name=display_name,
            )
            self.registry.set_state(runtime_key, "starting")
            self._stop_requested.discard(runtime_key)
            future = asyncio.run_coroutine_threadsafe(
                self._run_guarded(runtime_key, runner_factory, restart_policy or RestartPolicy()),
                self._required_loop(),
            )
            self._futures[runtime_key] = future
        self._record(
            runtime_key, "runner_start", summary="Channel runner started",
            details={"shop_key": shop_key, "channel": channel, "account_key": account_key},
        )

    def stop_runner(self, runtime_key: str, timeout: float = 10.0) -> None:
        with self._lock:
            future = self._futures.get(runtime_key)
            runner = self._runners.get(runtime_key)
            if future is None:
                return
            self._stop_requested.add(runtime_key)
        self.registry.set_state(runtime_key, "stopping")
        if runner is not None:
            stop_future = asyncio.run_coroutine_threadsafe(runner.stop(), self._required_loop())
            try:
                stop_future.result(timeout=timeout)
            except Exception:
                stop_future.cancel()
        try:
            future.result(timeout=timeout)
        except FutureTimeoutError:
            future.cancel()
        except Exception:
            pass
        with self._lock:
            self._runners.pop(runtime_key, None)
            self._futures.pop(runtime_key, None)
            self._stop_requested.discard(runtime_key)
        self.registry.set_state(runtime_key, "disconnected")
        self._record(runtime_key, "runner_stop", summary="Channel runner stopped")

    def stop_all(self, timeout: float = 10.0) -> None:
        with self._lock:
            keys = list(self._futures)
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

    async def _run_guarded(
        self,
        runtime_key: str,
        runner_factory: Callable[[], AsyncChannelRunner],
        policy: RestartPolicy,
    ) -> None:
        restart_count = 0
        delay = policy.initial_delay
        while not self._is_stopping(runtime_key):
            self.registry.set_state(runtime_key, "connecting")
            runner: AsyncChannelRunner | None = None
            try:
                runner = runner_factory()
                with self._lock:
                    self._runners[runtime_key] = runner
                self.registry.set_state(runtime_key, "connected")
                await runner.run()
                if self._is_stopping(runtime_key):
                    break
                error = RuntimeError("channel runner exited unexpectedly")
            except asyncio.CancelledError:
                self.registry.set_state(runtime_key, "disconnected")
                raise
            except Exception as exc:
                error = exc
            finally:
                with self._lock:
                    if runner is not None and self._runners.get(runtime_key) is runner:
                        self._runners.pop(runtime_key, None)

            if self._is_stopping(runtime_key):
                break
            if restart_count >= policy.max_restarts:
                self.registry.set_state(runtime_key, "error", error=str(error))
                self._record(
                    runtime_key,
                    "runner_failed",
                    result="error",
                    summary="Channel runner reached the restart limit",
                    details={"error": str(error), "restart_count": restart_count},
                )
                return
            restart_count += 1
            self.registry.set_state(runtime_key, "reconnecting", error=str(error))
            self._record(
                runtime_key,
                "runner_restart",
                result="warning",
                summary="Channel runner will be restarted",
                details={"error": str(error), "restart_count": restart_count, "delay_seconds": delay},
            )
            if await self._wait_for_restart(runtime_key, delay):
                break
            delay = min(policy.max_delay, max(policy.initial_delay, delay * policy.multiplier))
        self.registry.set_state(runtime_key, "disconnected")

    async def _wait_for_restart(self, runtime_key: str, delay: float) -> bool:
        remaining = max(0.0, delay)
        while remaining > 0:
            if self._is_stopping(runtime_key):
                return True
            interval = min(0.1, remaining)
            await asyncio.sleep(interval)
            remaining -= interval
        return self._is_stopping(runtime_key)

    def _is_stopping(self, runtime_key: str) -> bool:
        with self._lock:
            return runtime_key in self._stop_requested

    def _record(
        self,
        runtime_key: str,
        action: str,
        *,
        result: str = "success",
        summary: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        if self.operation_log:
            self.operation_log.record(
                "runtime", action, result=result, summary=summary,
                runtime_key=runtime_key, details=details,
            )

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
