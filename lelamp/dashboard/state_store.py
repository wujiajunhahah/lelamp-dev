"""In-memory state store for the dashboard."""

from __future__ import annotations

from copy import deepcopy
from threading import Lock
from time import time
from typing import Any


def _now_ms() -> int:
    return int(time() * 1000)


_DEFAULT_STATE_TEMPLATE = {
    "system": {
        "status": "unknown",
        "active_action": None,
        "last_update_ms": 0,
        "uptime_s": 0,
        "server_started_at": 0,
        "reachable_urls": [],
    },
    "motion": {
        "status": "unknown",
        "current_recording": None,
        "last_completed_recording": None,
        "home_recording": None,
        "startup_recording": None,
        "last_result": None,
        "motors_connected": "unknown",
        "calibration_state": "unknown",
        "available_recordings": [],
    },
    "light": {
        "status": "unknown",
        "color": None,
        "effect": None,
        "brightness": None,
        "last_result": None,
    },
    "audio": {
        "status": "unknown",
        "output_device": None,
        "volume_percent": None,
        "last_result": None,
    },
    "errors": [],
}

DEFAULT_STATE = deepcopy(_DEFAULT_STATE_TEMPLATE)


class DashboardStateStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._state = deepcopy(_DEFAULT_STATE_TEMPLATE)
        self._state["system"]["last_update_ms"] = _now_ms()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._state)

    def patch(self, section: str, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            target = self._state.get(section)
            if not isinstance(target, dict):
                raise KeyError(section)

            target.update(deepcopy(values))
            self._state["system"]["last_update_ms"] = _now_ms()
            return deepcopy(self._state)

    def set_system(self, **values: Any) -> dict[str, Any]:
        return self.patch("system", values)

    def record_error(
        self,
        code: str,
        message: str,
        source: str,
        severity: str,
    ) -> dict[str, Any]:
        with self._lock:
            now_ms = _now_ms()
            errors = self._state["errors"]

            for index, error in enumerate(errors):
                if error["code"] == code and error["source"] == source:
                    error["message"] = message
                    error["severity"] = severity
                    error["active"] = True
                    error["last_seen_ms"] = now_ms
                    if index != 0:
                        errors.insert(0, errors.pop(index))
                    self._state["system"]["last_update_ms"] = now_ms
                    return deepcopy(self._state)

            errors.insert(
                0,
                {
                    "code": code,
                    "message": message,
                    "source": source,
                    "severity": severity,
                    "active": True,
                    "first_seen_ms": now_ms,
                    "last_seen_ms": now_ms,
                },
            )
            self._state["system"]["last_update_ms"] = now_ms
            return deepcopy(self._state)
