"""Typed adapter over the dashboard runtime services."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from lelamp import remote_control
from lelamp.service.motors.animation_service import AnimationService
from lelamp.service.rgb.rgb_service import RGBService


@dataclass(frozen=True)
class DashboardActionResult:
    ok: bool
    message: str
    detail: str | None = None


class DashboardRuntimeBridge:
    def __init__(
        self,
        settings,
        animation_factory=AnimationService,
        rgb_factory=RGBService,
        remote_module=remote_control,
    ) -> None:
        self.settings = settings
        self.animation_factory = animation_factory
        self.rgb_factory = rgb_factory
        self.remote_module = remote_module

    def list_recordings(self) -> list[str]:
        service = self._build_animation_service()
        return service.get_available_recordings()

    def startup(self) -> DashboardActionResult:
        return self._run_remote(
            self.remote_module._handle_startup,
            recording=self.settings.startup_recording,
            home_recording=self.settings.home_recording,
            settle_frames=self.remote_module.DEFAULT_STARTUP_SETTLE_FRAMES,
            settle_hold_frames=self.remote_module.DEFAULT_STARTUP_HOLD_FRAMES,
            settle_fps=self.remote_module.DEFAULT_STARTUP_FPS,
            wake_fps=self.remote_module.DEFAULT_WAKE_FPS,
            post_wake_hold=self.remote_module.DEFAULT_POST_WAKE_HOLD_SECONDS,
        )

    def play(self, recording_name: str) -> DashboardActionResult:
        service = self._build_animation_service()
        recordings = set(service.get_available_recordings())

        if recording_name not in recordings:
            return DashboardActionResult(False, "Recording not found", detail=recording_name)

        service.start()
        try:
            service.dispatch("play", recording_name)
            if not service.wait_until_playback_complete(timeout=120.0):
                return DashboardActionResult(
                    False,
                    "Timed out waiting for playback to finish",
                    detail=recording_name,
                )
        except Exception as exc:
            return DashboardActionResult(False, "Playback failed", detail=str(exc))
        finally:
            service.stop()

        return DashboardActionResult(True, "Playback finished", detail=recording_name)

    def shutdown_pose(self) -> DashboardActionResult:
        return self._run_remote(
            self.remote_module._handle_shutdown,
            recording="power_off",
            prepare_fraction=self.remote_module.DEFAULT_SHUTDOWN_PREPARE_FRACTION,
            prepare_frames=self.remote_module.DEFAULT_SHUTDOWN_PREPARE_FRAMES,
            settle_frames=self.remote_module.DEFAULT_SHUTDOWN_SETTLE_FRAMES,
            hold_frames=self.remote_module.DEFAULT_SHUTDOWN_HOLD_FRAMES,
            fps=self.remote_module.DEFAULT_SHUTDOWN_FPS,
            final_hold=self.remote_module.DEFAULT_SHUTDOWN_FINAL_HOLD_SECONDS,
            release_pause=self.remote_module.DEFAULT_RELEASE_PAUSE_SECONDS,
            keep_led_on=False,
        )

    def stop(self) -> DashboardActionResult:
        return self.play(self.settings.home_recording)

    def set_light_solid(self, rgb: tuple[int, int, int]) -> DashboardActionResult:
        service = self._build_rgb_service()
        try:
            service.handle_event("solid", rgb)
        except Exception as exc:
            return DashboardActionResult(False, "Failed to set solid light", detail=str(exc))
        finally:
            service.stop()

        return DashboardActionResult(True, "Solid light applied", detail=str(rgb))

    def clear_light(self) -> DashboardActionResult:
        service = self._build_rgb_service()
        try:
            service.clear()
        except Exception as exc:
            return DashboardActionResult(False, "Failed to clear light", detail=str(exc))
        finally:
            service.stop()

        return DashboardActionResult(True, "Light cleared")

    def _run_remote(self, handler, **overrides: Any) -> DashboardActionResult:
        args = SimpleNamespace(
            id=self.settings.lamp_id,
            port=self.settings.port,
            fps=self.settings.fps,
            enable_rgb=self.settings.enable_rgb,
            led_count=self.settings.led_count,
            led_pin=self.settings.led_pin,
            led_freq_hz=self.settings.led_freq_hz,
            led_dma=self.settings.led_dma,
            led_brightness=self.settings.led_brightness,
            led_invert=self.settings.led_invert,
            led_channel=self.settings.led_channel,
            **overrides,
        )

        try:
            exit_code = handler(args)
        except Exception as exc:
            return DashboardActionResult(False, "Runtime action failed", detail=str(exc))

        if exit_code != 0:
            return DashboardActionResult(
                False,
                "Runtime action returned a non-zero exit code",
                detail=str(exit_code),
            )

        return DashboardActionResult(True, "Runtime action completed")

    def _build_animation_service(self):
        return self.animation_factory(
            port=self.settings.port,
            lamp_id=self.settings.lamp_id,
            fps=self.settings.fps,
            duration=self.settings.interpolation_duration,
            idle_recording=self.settings.home_recording,
            home_recording=self.settings.home_recording,
            use_home_pose_relative=self.settings.use_home_pose_relative,
        )

    def _build_rgb_service(self):
        return self.rgb_factory(
            led_count=self.settings.led_count,
            led_pin=self.settings.led_pin,
            led_freq_hz=self.settings.led_freq_hz,
            led_dma=self.settings.led_dma,
            led_brightness=self.settings.led_brightness,
            led_invert=self.settings.led_invert,
            led_channel=self.settings.led_channel,
        )
