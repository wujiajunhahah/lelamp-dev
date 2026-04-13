"""Serialized action execution for dashboard operators."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock, Thread
from typing import Callable

from lelamp.dashboard.runtime_bridge import DashboardActionResult
from lelamp.dashboard.state_store import DashboardStateStore


@dataclass(frozen=True)
class DashboardActionReceipt:
    ok: bool
    action_id: str
    state: str
    message: str
    error: str | None = None


class DashboardActionExecutor:
    def __init__(self, store: DashboardStateStore) -> None:
        self._store = store
        self._lock = Lock()
        self._worker: Thread | None = None
        self._active_action: str | None = None

    def submit(
        self,
        action_id: str,
        callback: Callable[[], DashboardActionResult],
        *,
        section: str,
        success_patch: dict[str, object],
    ) -> DashboardActionReceipt:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return DashboardActionReceipt(
                    False,
                    action_id,
                    "busy",
                    "Another action is already running.",
                    error="busy",
                )

            self._active_action = action_id
            self._store.set_system(status="running", active_action=action_id)
            self._store.patch(section, {"status": "running", "last_result": None})

            worker = Thread(
                target=self._run_action,
                args=(action_id, callback, section, success_patch),
                daemon=True,
            )
            self._worker = worker
            worker.start()

        return DashboardActionReceipt(True, action_id, "running", f"{action_id} started.")

    def current_action(self) -> str | None:
        with self._lock:
            return self._active_action

    def is_busy(self) -> bool:
        with self._lock:
            return self._worker is not None and self._worker.is_alive()

    def wait_for_idle(self, timeout: float | None = None) -> bool:
        with self._lock:
            worker = self._worker

        if worker is None:
            return True

        worker.join(timeout=timeout)
        return not worker.is_alive()

    def _run_action(
        self,
        action_id: str,
        callback: Callable[[], DashboardActionResult],
        section: str,
        success_patch: dict[str, object],
    ) -> None:
        try:
            result = callback()
            if result.ok:
                self._store.patch(section, dict(success_patch, last_result=result.message))
                self._store.set_system(status="ready", active_action=None)
                return

            self._store.patch(section, {"status": "error", "last_result": result.message})
            self._store.record_error(f"action.{action_id}", result.message, section, "error")
            self._store.set_system(status="error", active_action=None)
        except Exception as exc:
            message = str(exc)
            self._store.patch(section, {"status": "error", "last_result": message})
            self._store.record_error(f"action.{action_id}", message, section, "error")
            self._store.set_system(status="error", active_action=None)
        finally:
            with self._lock:
                self._active_action = None
                if self._worker is not None and not self._worker.is_alive():
                    self._worker = None
