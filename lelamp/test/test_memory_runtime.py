from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_bootstrap_agent_runtime_returns_noop_when_disabled(monkeypatch):
    from lelamp.memory import runtime as memruntime

    monkeypatch.setenv("LELAMP_MEMORY_DISABLE", "1")

    runtime = memruntime.bootstrap_agent_runtime(
        SimpleNamespace(model_provider="qwen")
    )

    assert runtime.enabled is False
    runtime.set_motor_bus_enabled(True)
    runtime.close()


def test_bootstrap_agent_runtime_runs_selfcheck_and_starts_session(monkeypatch):
    from lelamp.memory import runtime as memruntime

    events = []

    class FakeWriter:
        pass

    class FakeHandle:
        session_id = "sess_2026-04-18_12-00-00"

        def close(self, *, end_ts_ms=None):
            events.append(("handle.close", end_ts_ms))

    def fake_writer(user_id=None):
        events.append(("writer", user_id))
        return FakeWriter()

    def fake_selfcheck(writer):
        assert isinstance(writer, FakeWriter)
        events.append("selfcheck")
        return SimpleNamespace(recent_index_rebuilt=False)

    def fake_start_agent_session(writer, *, model_providers=(), now=None, pid=None, git_ref=None):
        assert isinstance(writer, FakeWriter)
        events.append(("start_agent_session", tuple(model_providers)))
        return FakeHandle()

    monkeypatch.delenv("LELAMP_MEMORY_DISABLE", raising=False)
    monkeypatch.setattr(memruntime, "MemoryWriter", fake_writer)
    monkeypatch.setattr(memruntime, "run_selfcheck", fake_selfcheck)
    monkeypatch.setattr(memruntime, "start_agent_session", fake_start_agent_session)

    runtime = memruntime.bootstrap_agent_runtime(
        SimpleNamespace(model_provider="glm")
    )

    assert runtime.enabled is True
    assert events == [
        ("writer", None),
        "selfcheck",
        ("start_agent_session", ("glm",)),
    ]


def test_bootstrap_agent_runtime_degrades_to_noop_on_failure(monkeypatch):
    from lelamp.memory import runtime as memruntime

    monkeypatch.delenv("LELAMP_MEMORY_DISABLE", raising=False)
    monkeypatch.setattr(memruntime, "MemoryWriter", lambda user_id=None: (_ for _ in ()).throw(RuntimeError("disk broke")))

    runtime = memruntime.bootstrap_agent_runtime(
        SimpleNamespace(model_provider="qwen")
    )

    assert runtime.enabled is False
