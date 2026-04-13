"""Runtime sampler loop for the dashboard."""

from __future__ import annotations

from threading import Event, Thread
from time import time

from .audio import collect_audio_snapshot
from .motors import collect_motor_snapshot
from .network import build_reachable_urls


def collect_runtime_snapshot(settings, executor, started_at: float) -> dict[str, object]:
    return {
        "status": "running" if executor.is_busy() else "ready",
        "active_action": executor.current_action(),
        "uptime_s": int(time() - started_at),
        "server_started_at": int(started_at * 1000),
        "reachable_urls": build_reachable_urls(
            settings.dashboard_host,
            settings.dashboard_port,
        ),
    }


class DashboardSamplerLoop:
    def __init__(
        self,
        store,
        settings,
        bridge,
        executor,
        *,
        started_at: float | None = None,
    ) -> None:
        self._store = store
        self._settings = settings
        self._bridge = bridge
        self._executor = executor
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._started_at = time() if started_at is None else started_at
        self.interval_s = max(self._settings.dashboard_poll_ms / 1000.0, 0.2)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._store.patch(
                "system",
                collect_runtime_snapshot(
                    self._settings,
                    self._executor,
                    self._started_at,
                ),
            )
            self._store.patch(
                "motion",
                collect_motor_snapshot(self._settings, self._bridge),
            )
            self._store.patch(
                "audio",
                collect_audio_snapshot(self._settings),
            )
            self._stop_event.wait(self.interval_s)
