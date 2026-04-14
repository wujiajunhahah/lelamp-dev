from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_GLM_PROVIDER_ALIASES = {"glm", "zhipu", "bigmodel", "z.ai"}
_OPENAI_BASE_URL = "https://api.openai.com/v1"
_GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"


def _get_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _get_optional_str(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return value


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _get_positive_int(name: str, default: int) -> int:
    value = _get_int(name, default)
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return value


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


def _normalize_model_provider(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in _GLM_PROVIDER_ALIASES:
        return "glm"
    if normalized == "":
        return "glm"
    return normalized


def _get_model_provider() -> str:
    provider = _get_optional_str("MODEL_PROVIDER")
    if provider is not None:
        return _normalize_model_provider(provider)

    if os.getenv("ZAI_API_KEY"):
        return "glm"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "glm"


def _get_model_api_key() -> str | None:
    for env_name in ("MODEL_API_KEY", "ZAI_API_KEY", "OPENAI_API_KEY"):
        value = _get_optional_str(env_name)
        if value:
            return value
    return None


def _default_model_base_url(provider: str) -> str | None:
    if provider == "glm":
        return _GLM_BASE_URL
    if provider == "openai":
        return _OPENAI_BASE_URL
    return None


def _default_model_name(provider: str) -> str | None:
    if provider == "glm":
        return "glm-realtime"
    return None


def _default_model_voice(provider: str) -> str:
    if provider == "glm":
        return "tongtong"
    if provider == "openai":
        return "ballad"
    return "tongtong"


@dataclass(frozen=True)
class RuntimeSettings:
    port: str
    lamp_id: str
    fps: int
    dashboard_host: str
    dashboard_port: int
    dashboard_poll_ms: int
    model_provider: str
    model_api_key: str | None
    model_base_url: str | None
    model_name: str | None
    model_voice: str
    led_count: int
    led_pin: int
    led_freq_hz: int
    led_dma: int
    led_brightness: int
    led_invert: bool
    led_channel: int
    enable_rgb: bool
    startup_volume: int
    startup_recording: str
    idle_recording: str
    home_recording: str
    use_home_pose_relative: bool
    interpolation_duration: float
    audio_user: str


def load_runtime_settings() -> RuntimeSettings:
    load_dotenv(dotenv_path=".env", override=False)
    model_provider = _get_model_provider()

    idle_recording = _get_str("LELAMP_IDLE_RECORDING", "idle")

    return RuntimeSettings(
        port=_get_str("LELAMP_PORT", "/dev/ttyACM0"),
        lamp_id=_get_str("LELAMP_ID", "lelamp"),
        fps=_get_int("LELAMP_FPS", 30),
        dashboard_host=_get_str("LELAMP_DASHBOARD_HOST", "0.0.0.0"),
        dashboard_port=_get_positive_int("LELAMP_DASHBOARD_PORT", 8765),
        dashboard_poll_ms=_get_positive_int("LELAMP_DASHBOARD_POLL_MS", 400),
        model_provider=model_provider,
        model_api_key=_get_model_api_key(),
        model_base_url=_get_optional_str("MODEL_BASE_URL") or _default_model_base_url(model_provider),
        model_name=_get_optional_str("MODEL_NAME") or _default_model_name(model_provider),
        model_voice=_get_str("MODEL_VOICE", _default_model_voice(model_provider)),
        led_count=_get_int("LELAMP_LED_COUNT", 40),
        led_pin=_get_int("LELAMP_LED_PIN", 12),
        led_freq_hz=_get_int("LELAMP_LED_FREQ_HZ", 800000),
        led_dma=_get_int("LELAMP_LED_DMA", 10),
        led_brightness=_get_int("LELAMP_LED_BRIGHTNESS", 255),
        led_invert=_get_bool("LELAMP_LED_INVERT", False),
        led_channel=_get_int("LELAMP_LED_CHANNEL", 0),
        enable_rgb=_get_bool("LELAMP_ENABLE_RGB", True),
        startup_volume=_get_int("LELAMP_STARTUP_VOLUME", 100),
        startup_recording=_get_str("LELAMP_STARTUP_RECORDING", "wake_up"),
        idle_recording=idle_recording,
        home_recording=_get_str("LELAMP_HOME_RECORDING", idle_recording),
        use_home_pose_relative=_get_bool("LELAMP_USE_HOME_POSE_RELATIVE", False),
        interpolation_duration=_get_float("LELAMP_INTERPOLATION_DURATION", 3.0),
        audio_user=_get_str(
            "LELAMP_AUDIO_USER",
            os.getenv("SUDO_USER") or os.getenv("USER") or "pi",
        ),
    )


def build_realtime_model_config(settings: RuntimeSettings) -> dict[str, object]:
    kwargs: dict[str, object] = {"voice": settings.model_voice}

    if settings.model_name:
        kwargs["model"] = settings.model_name
    if settings.model_api_key:
        kwargs["api_key"] = settings.model_api_key
    if settings.model_base_url:
        kwargs["base_url"] = settings.model_base_url

    return kwargs
