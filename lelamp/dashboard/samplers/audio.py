"""Best-effort audio sampling for the dashboard."""

from __future__ import annotations

import re
import subprocess


_VOLUME_PATTERN = re.compile(r"\[(\d{1,3})%\]")


def collect_audio_snapshot(settings, *, run_command=subprocess.run) -> dict[str, object]:
    try:
        result = run_command(
            ["sudo", "-u", settings.audio_user, "amixer", "sget", "Line"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return {
            "status": "unknown",
            "output_device": "Line",
            "volume_percent": None,
            "last_result": None,
        }

    match = _VOLUME_PATTERN.search(result.stdout)
    if match is None:
        return {
            "status": "unknown",
            "output_device": "Line",
            "volume_percent": None,
            "last_result": None,
        }

    volume = int(match.group(1))
    return {
        "status": "ready" if volume > 0 else "muted",
        "output_device": "Line",
        "volume_percent": volume,
        "last_result": "sampled from amixer",
    }
