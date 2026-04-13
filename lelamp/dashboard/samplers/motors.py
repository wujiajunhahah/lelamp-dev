"""Motor sampling helpers for the dashboard."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path


def collect_motor_snapshot(
    settings,
    bridge,
    *,
    path_exists=None,
    current_motion: dict[str, object] | None = None,
) -> dict[str, object]:
    if path_exists is None:
        path_exists = Path.exists

    snapshot = {
        "status": "unknown",
        "current_recording": None,
        "last_completed_recording": None,
        "home_recording": settings.home_recording,
        "startup_recording": settings.startup_recording,
        "last_result": None,
        "motors_connected": "unknown",
        "calibration_state": "unknown",
        "available_recordings": [],
    }
    if current_motion is not None:
        snapshot.update(deepcopy(current_motion))

    recordings_error = False
    try:
        recordings = bridge.list_recordings()
    except Exception:
        recordings = []
        recordings_error = True

    port_path = Path(settings.port)
    port_present = path_exists(port_path)
    motors_connected: bool | str = port_present
    status = "idle" if port_present else "warning"

    if recordings_error and port_present:
        motors_connected = "unknown"
        status = "unknown"

    if current_motion is None or snapshot.get("status") not in {"running", "error"}:
        snapshot["status"] = status

    snapshot.update(
        {
            "home_recording": settings.home_recording,
            "startup_recording": settings.startup_recording,
            "motors_connected": motors_connected,
            "calibration_state": "unknown",
            "available_recordings": recordings,
        }
    )
    return snapshot
