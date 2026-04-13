"""Motor sampling helpers for the dashboard."""

from __future__ import annotations

from pathlib import Path


def collect_motor_snapshot(settings, bridge, *, path_exists=None) -> dict[str, object]:
    if path_exists is None:
        path_exists = Path.exists

    try:
        recordings = bridge.list_recordings()
    except Exception:
        recordings = []

    port_path = Path(settings.port)
    motors_connected = path_exists(port_path)

    return {
        "status": "idle" if motors_connected else "warning",
        "current_recording": None,
        "last_completed_recording": None,
        "home_recording": settings.home_recording,
        "startup_recording": settings.startup_recording,
        "last_result": None,
        "motors_connected": motors_connected,
        "calibration_state": "unknown",
        "available_recordings": recordings,
    }
