from __future__ import annotations

import asyncio
import time

from ai_store_support.bridge import BridgeSupervisor, RestartPolicy
from ai_store_support.runtime_status import RuntimeStatusRegistry


class FakeRunner:
    def __init__(self):
        self.stop_event: asyncio.Event | None = None

    async def run(self) -> None:
        self.stop_event = asyncio.Event()
        await self.stop_event.wait()

    async def stop(self) -> None:
        if self.stop_event is not None:
            self.stop_event.set()


def wait_for(predicate, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError("condition timed out")


def test_runtime_registry_counters():
    registry = RuntimeStatusRegistry()
    registry.register("demo:pdd:1", shop_key="demo", channel="pinduoduo", account_key="1", display_name="售前")
    registry.set_state("demo:pdd:1", "starting")
    registry.set_state("demo:pdd:1", "connected")
    registry.record_received("demo:pdd:1", 2)
    registry.record_sent("demo:pdd:1")
    registry.record_handoff("demo:pdd:1")

    row = registry.get("demo:pdd:1")
    assert row is not None
    assert row["state"] == "connected"
    assert row["received_messages"] == 2
    assert row["sent_messages"] == 1
    assert row["handoffs"] == 1
    assert row["connected_at"]


def test_bridge_supervisor_lifecycle():
    registry = RuntimeStatusRegistry()
    supervisor = BridgeSupervisor(registry)
    runner = FakeRunner()

    supervisor.start_runner(
        runtime_key="demo:pdd:1", shop_key="demo", channel="pinduoduo",
        account_key="1", display_name="售前", runner=runner,
    )
    wait_for(lambda: registry.get("demo:pdd:1")["state"] == "connected")
    supervisor.stop_runner("demo:pdd:1")
    assert registry.get("demo:pdd:1")["state"] == "disconnected"
    supervisor.stop_all()


def test_guarded_runner_restarts_after_failure():
    registry = RuntimeStatusRegistry()
    supervisor = BridgeSupervisor(registry)
    attempts = []

    class FlakyRunner(FakeRunner):
        async def run(self) -> None:
            attempts.append(len(attempts) + 1)
            if len(attempts) < 3:
                raise RuntimeError("temporary disconnect")
            await super().run()

    supervisor.start_guarded_runner(
        runtime_key="demo:pdd:guarded",
        shop_key="demo",
        channel="pinduoduo",
        account_key="guarded",
        runner_factory=FlakyRunner,
        restart_policy=RestartPolicy(max_restarts=4, initial_delay=0.01, max_delay=0.02),
    )
    wait_for(
        lambda: len(attempts) >= 3
        and registry.get("demo:pdd:guarded")["state"] == "connected"
    )
    assert registry.get("demo:pdd:guarded")["reconnects"] == 2
    supervisor.stop_runner("demo:pdd:guarded")
    supervisor.stop_all()
