from __future__ import annotations

import getpass
import os


_DEFAULT_MIXER_CONTROLS = ("PCM", "Line", "Line DAC", "HP", "HP DAC")


def build_amixer_volume_commands(
    *,
    audio_user: str,
    card_index: int,
    volume_percent: int,
    controls: tuple[str, ...] = _DEFAULT_MIXER_CONTROLS,
) -> list[list[str]]:
    current_user = getpass.getuser()
    should_use_sudo = os.geteuid() == 0 and current_user != audio_user
    command_prefix = ["sudo", "-u", audio_user] if should_use_sudo else []

    return [
        command_prefix
        + ["amixer", "-c", str(card_index), "sset", control, f"{volume_percent}%"]
        for control in controls
    ]
