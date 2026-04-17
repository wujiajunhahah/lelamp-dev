"""recent_index.json builder.

Contract anchors:

* ``LIFECYCLE.md#Recent Window`` -- cap = 3 agent sessions, 200 events
* ``LIFECYCLE.md#\u4e3a\u4ec0\u4e48 manual session \u7684\u4e8b\u4ef6\u4e5f\u8981\u8fc7\u6ee4\u6389`` --
  manual session events + summaries must never leak into the prompt
  read path.  This is enforced *here*, so downstream readers can
  trust the index at face value.

Building the index is a **writer-only** operation (LIFECYCLE.md
§"Reader \u6c38\u4e0d\u53c2\u4e0e\u91cd\u5efa").  Readers that need a degraded view scan
``sessions/*.summary.json`` directly without ever writing to disk.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from pathlib import Path
from typing import Any

from . import ids as _ids
from .session import _atomic_write_json
from .writer import MemoryWriter

_logger = logging.getLogger(__name__)

RECENT_INDEX_SCHEMA = "lelamp.memory.v0.recent_index"
RECENT_SESSION_LIMIT = 3
RECENT_EVENT_TAIL_LIMIT = 200


def recent_index_path(writer: MemoryWriter) -> Path:
    return writer.user_dir / "recent_index.json"


def _collect_agent_summary_entries(writer: MemoryWriter) -> list[dict[str, Any]]:
    """Return the newest ``RECENT_SESSION_LIMIT`` agent summary refs."""

    sessions_dir = writer.user_dir / "sessions"
    if not sessions_dir.exists():
        return []
    candidates: list[tuple[int, str, Path]] = []
    for path in sessions_dir.glob("*.summary.json"):
        try:
            with path.open("r", encoding="utf-8") as fh:
                summary = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            _logger.warning("skipping unreadable summary %s: %s", path, exc)
            continue
        session_id = summary.get("session_id")
        if not isinstance(session_id, str):
            continue
        if _ids.is_manual_session(session_id):
            continue
        start_ts_ms = int(summary.get("start_ts_ms") or 0)
        candidates.append((start_ts_ms, session_id, path))
    candidates.sort(reverse=True)
    refs: list[dict[str, Any]] = []
    for _, session_id, path in candidates[:RECENT_SESSION_LIMIT]:
        refs.append(
            {
                "session_id": session_id,
                "summary_ref": f"sessions/{path.name}",
            }
        )
    return refs


def _collect_event_tail_refs(writer: MemoryWriter) -> list[dict[str, Any]]:
    """Return the last ``RECENT_EVENT_TAIL_LIMIT`` non-manual event refs.

    The projection is intentionally minimal (``event_id`` /
    ``kind`` / ``ts_ms``): the prompt builder opens the full
    ``events.jsonl`` itself when it needs payloads, and keeping the
    index tiny means recent_index rebuilds stay ~1 ms on the Pi.
    """

    tail: deque[dict[str, Any]] = deque(maxlen=RECENT_EVENT_TAIL_LIMIT)
    for event in writer.iter_events():
        session_id = event.get("session_id")
        if not isinstance(session_id, str):
            continue
        if _ids.is_manual_session(session_id):
            continue
        ev_id = event.get("event_id")
        kind = event.get("kind")
        ts_ms = event.get("ts_ms")
        if not isinstance(ev_id, str) or not isinstance(kind, str):
            continue
        if not isinstance(ts_ms, int):
            continue
        tail.append({"event_id": ev_id, "kind": kind, "ts_ms": ts_ms})
    return list(tail)


def build_recent_index(writer: MemoryWriter) -> dict[str, Any]:
    """Compute the index payload without touching disk (test seam)."""

    return {
        "schema": RECENT_INDEX_SCHEMA,
        "built_at_ms": _ids.current_timestamp_ms(),
        "sessions": _collect_agent_summary_entries(writer),
        "event_tail_refs": _collect_event_tail_refs(writer),
    }


def rebuild_recent_index(writer: MemoryWriter) -> Path:
    """Recompute and atomically persist ``recent_index.json``.

    Safe to call at any point; the LIFECYCLE-mandated trigger points
    are "after each session's summary write" and "at writer startup
    self-check".  Both go through here.
    """

    payload = build_recent_index(writer)
    path = recent_index_path(writer)
    _atomic_write_json(path, payload)
    return path


def load_recent_index(writer: MemoryWriter) -> dict[str, Any]:
    with recent_index_path(writer).open("r", encoding="utf-8") as fh:
        return json.load(fh)
