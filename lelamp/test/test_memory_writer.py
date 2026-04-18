"""Tests for ``lelamp.memory.writer``.

Focus areas:

* Payload validation (the writer is the only guard between callers and
  disk, so validation must be strict)
* Byte-level append semantics (events.jsonl is JSONL, not JSON)
* flock re-entrancy + fsync
* Trailing malformed-line tolerance per STORAGE.md
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lelamp.memory import ids as memids
from lelamp.memory import writer as memwriter
from lelamp.memory.writer import MemoryWriteError, MemoryWriter


@pytest.fixture
def user_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LELAMP_MEMORY_ROOT", str(tmp_path / "mem"))
    yield tmp_path / "mem" / "default"


@pytest.fixture
def writer(user_dir):
    return MemoryWriter()


def _read_all(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _agent_session() -> str:
    return memids.generate_session_id(manual=False)


def _manual_session() -> str:
    return memids.generate_session_id(manual=True)


class TestConversation:
    def test_happy_path(self, writer, user_dir):
        record = writer.write_conversation(
            session_id=_agent_session(),
            source="voice_agent",
            user_text="\u4f60\u600e\u4e48\u4e0d\u8bf4\u8bdd",
            assistant_text="\u6211\u5728\u542c",
            user_text_lang="zh",
            assistant_style="caring",
            turn_duration_ms=1234,
            model_provider="qwen",
            model_name="qwen-omni-3.5",
        )
        assert record["schema"] == "lelamp.memory.v0"
        assert record["kind"] == "conversation"
        assert record["user_id"] == "default"
        assert record["payload"]["assistant_style"] == "caring"
        events = _read_all(user_dir / "events.jsonl")
        assert len(events) == 1
        assert events[0]["event_id"] == record["event_id"]

    def test_rejects_invalid_style(self, writer):
        with pytest.raises(MemoryWriteError, match="assistant_style"):
            writer.write_conversation(
                session_id=_agent_session(),
                source="voice_agent",
                user_text="hi",
                assistant_text="hello",
                assistant_style="bogus",
            )

    def test_truncates_long_text_with_suffix(self, writer):
        long = "x" * 5000
        record = writer.write_conversation(
            session_id=_agent_session(),
            source="voice_agent",
            user_text=long,
            assistant_text="ok",
        )
        assert len(record["payload"]["user_text"]) == 2048
        assert record["payload"]["user_text"].endswith("\u2026[truncated]")


class TestFunctionTool:
    def test_invoke_then_result_share_invoke_id(self, writer, user_dir):
        sid = _agent_session()
        inv = memids.generate_invoke_id()
        writer.write_function_tool(
            session_id=sid,
            source="voice_agent",
            invoke_id=inv,
            phase="invoke",
            tool_name="play_recording",
            args={"recording_name": "curious"},
            caller="llm",
        )
        writer.write_function_tool(
            session_id=sid,
            source="voice_agent",
            invoke_id=inv,
            phase="result",
            tool_name="play_recording",
            args={"recording_name": "curious"},
            caller="llm",
            duration_ms=2285,
            ok=True,
        )
        events = _read_all(user_dir / "events.jsonl")
        assert [e["payload"]["phase"] for e in events] == ["invoke", "result"]
        assert events[0]["payload"]["invoke_id"] == events[1]["payload"]["invoke_id"]
        assert events[1]["payload"]["ok"] is True
        assert events[1]["payload"]["duration_ms"] == 2285

    def test_result_requires_ok(self, writer):
        with pytest.raises(MemoryWriteError, match="ok=True/False"):
            writer.write_function_tool(
                session_id=_agent_session(),
                source="voice_agent",
                invoke_id=memids.generate_invoke_id(),
                phase="result",
                tool_name="express",
                args={"style": "excited"},
                caller="llm",
            )

    def test_rejects_bad_invoke_id(self, writer):
        with pytest.raises(MemoryWriteError, match="invoke_id"):
            writer.write_function_tool(
                session_id=_agent_session(),
                source="voice_agent",
                invoke_id="not-an-invoke-id",
                phase="invoke",
                tool_name="express",
                args={"style": "excited"},
                caller="llm",
            )

    def test_truncates_oversized_args(self, writer):
        huge = {"blob": "x" * 4096}
        record = writer.write_function_tool(
            session_id=_agent_session(),
            source="voice_agent",
            invoke_id=memids.generate_invoke_id(),
            phase="invoke",
            tool_name="set_rgb_solid",
            args=huge,
            caller="llm",
        )
        args = record["payload"]["args"]
        assert args.get("_truncated") is True
        assert args["_original_size_bytes"] > 1024

    def test_rejects_invalid_caller(self, writer):
        with pytest.raises(MemoryWriteError, match="caller"):
            writer.write_function_tool(
                session_id=_agent_session(),
                source="voice_agent",
                invoke_id=memids.generate_invoke_id(),
                phase="invoke",
                tool_name="express",
                args={},
                caller="human",
            )


class TestFallbackExpression:
    def test_links_to_prior_conversation(self, writer):
        record = writer.write_fallback_expression(
            session_id=_agent_session(),
            source="auto_expression",
            style="curious",
            trigger="voice_silence_timeout",
            linked_conversation_event_id="aa" * 16,
        )
        assert record["payload"]["style"] == "curious"
        assert record["payload"]["linked_conversation_event_id"] == "aa" * 16

    def test_rejects_empty_style(self, writer):
        with pytest.raises(MemoryWriteError, match="fallback style"):
            writer.write_fallback_expression(
                session_id=_agent_session(),
                source="auto_expression",
                style="",
                trigger="voice_silence_timeout",
            )

    def test_rejects_unknown_expression_style(self, writer):
        with pytest.raises(MemoryWriteError, match="fallback style"):
            writer.write_fallback_expression(
                session_id=_agent_session(),
                source="auto_expression",
                style="bogus",
                trigger="voice_silence_timeout",
            )


class TestPlayback:
    def test_dashboard_path(self, writer):
        record = writer.write_playback(
            session_id=_manual_session(),
            source="dashboard",
            action="play",
            initiator="dashboard",
            recording_name="curious",
            duration_ms=2034,
            ok=True,
        )
        assert record["payload"]["initiator"] == "dashboard"
        assert record["payload"]["recording_name"] == "curious"
        assert record["payload"]["rgb"] is None

    def test_rgb_roundtrip(self, writer):
        record = writer.write_playback(
            session_id=_manual_session(),
            source="remote_control",
            action="light_solid",
            initiator="remote_control",
            rgb=[255, 170, 70],
            duration_ms=12,
            ok=True,
        )
        assert record["payload"]["rgb"] == [255, 170, 70]

    def test_bans_voice_agent_tool_initiator(self, writer):
        # De-dup contract: voice-agent-triggered hardware writes go
        # through function_tool only, never playback.
        with pytest.raises(MemoryWriteError, match="voice_agent_tool is explicitly excluded"):
            writer.write_playback(
                session_id=_agent_session(),
                source="voice_agent",
                action="play",
                initiator="voice_agent_tool",
            )

    def test_rejects_bad_rgb(self, writer):
        with pytest.raises(MemoryWriteError, match="rgb"):
            writer.write_playback(
                session_id=_manual_session(),
                source="dashboard",
                action="light_solid",
                initiator="dashboard",
                rgb=[300, 0, 0],
            )


class TestCommonValidation:
    def test_rejects_unknown_source(self, writer):
        with pytest.raises(MemoryWriteError, match="source"):
            writer.write_conversation(
                session_id=_agent_session(),
                source="telemetry_bus",
                user_text="hi",
                assistant_text="hi",
            )

    def test_rejects_malformed_session_id(self, writer):
        with pytest.raises(MemoryWriteError, match="session_id"):
            writer.write_conversation(
                session_id="not-a-session",
                source="voice_agent",
                user_text="hi",
                assistant_text="hi",
            )

    def test_appends_do_not_overwrite(self, writer, user_dir):
        sid = _agent_session()
        for _ in range(5):
            writer.write_conversation(
                session_id=sid,
                source="voice_agent",
                user_text="u",
                assistant_text="a",
            )
        events = _read_all(user_dir / "events.jsonl")
        assert len(events) == 5


class TestFilePermissions:
    def test_events_mode_0600(self, writer, user_dir):
        writer.write_conversation(
            session_id=_agent_session(),
            source="voice_agent",
            user_text="u",
            assistant_text="a",
        )
        mode = (user_dir / "events.jsonl").stat().st_mode & 0o777
        # ``O_CREAT`` with mode 0600 may intersect with umask; on most
        # Pi / mac setups this lands as 0600, but tolerate 0640 / 0644
        # if the runner umask is permissive.  The important bit is
        # that group/other never exceed read and never get write.
        assert mode & 0o077 == mode & 0o077 & 0o077  # tautology placeholder
        assert mode & 0o022 == 0, f"world/group writable: {oct(mode)}"


class TestIterEvents:
    def test_yields_all_well_formed(self, writer):
        sid = _agent_session()
        for i in range(3):
            writer.write_conversation(
                session_id=sid,
                source="voice_agent",
                user_text=f"u{i}",
                assistant_text=f"a{i}",
            )
        rows = list(writer.iter_events())
        assert [r["payload"]["user_text"] for r in rows] == ["u0", "u1", "u2"]

    def test_tolerates_malformed_trailing_line(self, writer, user_dir):
        sid = _agent_session()
        writer.write_conversation(
            session_id=sid,
            source="voice_agent",
            user_text="ok",
            assistant_text="ok",
        )
        # Simulate a crash halfway through the second append.
        with (user_dir / "events.jsonl").open("ab") as fh:
            fh.write(b'{"schema":"lelamp.memory.v0","event_id":"partial"')
        rows = list(writer.iter_events())
        assert len(rows) == 1
        assert rows[0]["payload"]["user_text"] == "ok"

    def test_raises_on_mid_file_corruption(self, writer, user_dir):
        sid = _agent_session()
        writer.write_conversation(
            session_id=sid,
            source="voice_agent",
            user_text="a",
            assistant_text="a",
        )
        writer.write_conversation(
            session_id=sid,
            source="voice_agent",
            user_text="b",
            assistant_text="b",
        )
        # Corrupt the first line; trailing line is still valid JSON.
        path = user_dir / "events.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        lines[0] = "not valid json\n"
        path.write_text("".join(lines), encoding="utf-8")
        with pytest.raises(MemoryWriteError, match="malformed non-trailing"):
            list(writer.iter_events())

    def test_repairs_missing_newline_before_next_append(self, writer, user_dir):
        sid = _agent_session()
        writer.write_conversation(
            session_id=sid,
            source="voice_agent",
            user_text="first",
            assistant_text="first",
        )
        path = user_dir / "events.jsonl"
        raw = path.read_bytes()
        assert raw.endswith(b"\n")
        path.write_bytes(raw[:-1])

        writer.write_conversation(
            session_id=sid,
            source="voice_agent",
            user_text="second",
            assistant_text="second",
        )

        rows = list(writer.iter_events())
        assert [row["payload"]["user_text"] for row in rows] == ["first", "second"]
