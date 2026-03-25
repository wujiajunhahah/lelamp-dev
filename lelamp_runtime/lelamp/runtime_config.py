from __future__ import annotations

from dataclasses import dataclass
import os


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _get_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a float, got {value!r}") from exc


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default

    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False

    raise ValueError(f"{name} must be a boolean, got {value!r}")


@dataclass(frozen=True)
class RuntimeSettings:
    port: str
    lamp_id: str
    fps: int
    led_count: int
    led_pin: int
    led_freq_hz: int
    led_dma: int
    led_brightness: int
    led_invert: bool
    led_channel: int
    startup_volume: int
    startup_recording: str
    idle_recording: str
    interpolation_duration: float
    audio_user: str


def load_runtime_settings() -> RuntimeSettings:
    return RuntimeSettings(
        port=_get_str("LELAMP_PORT", "/dev/ttyACM0"),
        lamp_id=_get_str("LELAMP_ID", "lelamp"),
        fps=_get_int("LELAMP_FPS", 30),
        led_count=_get_int("LELAMP_LED_COUNT", 40),
        led_pin=_get_int("LELAMP_LED_PIN", 12),
        led_freq_hz=_get_int("LELAMP_LED_FREQ_HZ", 800000),
        led_dma=_get_int("LELAMP_LED_DMA", 10),
        led_brightness=_get_int("LELAMP_LED_BRIGHTNESS", 255),
        led_invert=_get_bool("LELAMP_LED_INVERT", False),
        led_channel=_get_int("LELAMP_LED_CHANNEL", 0),
        startup_volume=_get_int("LELAMP_STARTUP_VOLUME", 100),
        startup_recording=_get_str("LELAMP_STARTUP_RECORDING", "wake_up"),
        idle_recording=_get_str("LELAMP_IDLE_RECORDING", "idle"),
        interpolation_duration=_get_float("LELAMP_INTERPOLATION_DURATION", 3.0),
        audio_user=_get_str(
            "LELAMP_AUDIO_USER",
            os.getenv("SUDO_USER") or os.getenv("USER") or "pi",
        ),
    )
