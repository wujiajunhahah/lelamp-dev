import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lelamp.dashboard import runtime_bridge as runtime_bridge_mod
from lelamp.dashboard.runtime_bridge import DashboardRuntimeBridge


class FakeAnimationService:
    instances = []
    available_recordings = ["curious", "wake_up"]
    wait_result = True
    raise_on_start: Exception | None = None
    raise_on_dispatch: Exception | None = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.started = False
        self.dispatched = []
        self.stopped = False
        FakeAnimationService.instances.append(self)

    def get_available_recordings(self) -> list[str]:
        return list(FakeAnimationService.available_recordings)

    def start(self) -> None:
        if FakeAnimationService.raise_on_start is not None:
            raise FakeAnimationService.raise_on_start
        self.started = True

    def dispatch(self, event_type: str, payload: str) -> None:
        if FakeAnimationService.raise_on_dispatch is not None:
            raise FakeAnimationService.raise_on_dispatch
        self.dispatched.append((event_type, payload))

    def wait_until_playback_complete(self, timeout: float | None = None) -> bool:
        return FakeAnimationService.wait_result

    def stop(self) -> None:
        self.stopped = True


class FakeRGBService:
    instances = []
    raise_on_handle_event: Exception | None = None
    raise_on_clear: Exception | None = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.actions = []
        FakeRGBService.instances.append(self)

    def handle_event(self, event_type: str, payload) -> None:
        if FakeRGBService.raise_on_handle_event is not None:
            raise FakeRGBService.raise_on_handle_event
        self.actions.append((event_type, payload))

    def clear(self) -> None:
        if FakeRGBService.raise_on_clear is not None:
            raise FakeRGBService.raise_on_clear
        self.actions.append(("clear", None))

    def stop(self) -> None:
        self.actions.append(("stop", None))


class ExplodingFactory:
    called = False

    def __new__(cls, **kwargs):
        cls.called = True
        raise RuntimeError("factory boom")


class ExplodingAnimationFactory:
    called = False

    def __new__(cls, **kwargs):
        cls.called = True
        raise RuntimeError("animation factory boom")


class DashboardRuntimeBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeAnimationService.instances = []
        FakeAnimationService.available_recordings = ["curious", "wake_up"]
        FakeAnimationService.wait_result = True
        FakeAnimationService.raise_on_start = None
        FakeAnimationService.raise_on_dispatch = None
        FakeRGBService.instances = []
        FakeRGBService.raise_on_handle_event = None
        FakeRGBService.raise_on_clear = None
        ExplodingFactory.called = False
        ExplodingAnimationFactory.called = False

    @staticmethod
    def _make_settings(enable_rgb: bool = True) -> SimpleNamespace:
        return SimpleNamespace(
            port="/dev/ttyACM0",
            lamp_id="lelamp",
            fps=30,
            interpolation_duration=3.0,
            startup_recording="wake_up",
            home_recording="home_safe",
            use_home_pose_relative=True,
            enable_rgb=enable_rgb,
            led_count=40,
            led_pin=12,
            led_freq_hz=800000,
            led_dma=10,
            led_brightness=255,
            led_invert=False,
            led_channel=0,
        )

    def test_play_uses_home_recording_as_idle_target(self) -> None:
        settings = self._make_settings()

        bridge = DashboardRuntimeBridge(
            settings,
            animation_factory=FakeAnimationService,
            rgb_factory=FakeRGBService,
            remote_module=SimpleNamespace(),
        )

        result = bridge.play("curious")

        service = FakeAnimationService.instances[-1]
        self.assertTrue(result.ok)
        self.assertEqual(service.kwargs["idle_recording"], "home_safe")
        self.assertEqual(service.kwargs["home_recording"], "home_safe")
        self.assertEqual(service.dispatched, [("play", "curious")])

    def test_play_missing_recording_fast_fails_without_dispatch(self) -> None:
        settings = self._make_settings()
        FakeAnimationService.available_recordings = ["wake_up"]

        bridge = DashboardRuntimeBridge(
            settings,
            animation_factory=FakeAnimationService,
            rgb_factory=FakeRGBService,
            remote_module=SimpleNamespace(),
        )

        result = bridge.play("curious")

        service = FakeAnimationService.instances[-1]
        self.assertFalse(result.ok)
        self.assertIn("not found", result.message.lower())
        self.assertEqual(result.detail, "curious")
        self.assertEqual(service.dispatched, [])
        self.assertFalse(service.started)
        self.assertFalse(service.stopped)

    def test_play_converts_service_exception_to_failed_result(self) -> None:
        settings = self._make_settings()
        FakeAnimationService.raise_on_start = RuntimeError("motor serial unavailable")

        bridge = DashboardRuntimeBridge(
            settings,
            animation_factory=FakeAnimationService,
            rgb_factory=FakeRGBService,
            remote_module=SimpleNamespace(),
        )

        result = bridge.play("curious")

        self.assertFalse(result.ok)
        self.assertIn("failed", result.message.lower())
        self.assertIn("unavailable", result.detail)

    def test_play_converts_animation_factory_failure_to_failed_result(self) -> None:
        settings = self._make_settings()

        bridge = DashboardRuntimeBridge(
            settings,
            animation_factory=ExplodingAnimationFactory,
            rgb_factory=FakeRGBService,
            remote_module=SimpleNamespace(),
        )

        result = bridge.play("curious")

        self.assertFalse(result.ok)
        self.assertIn("failed", result.message.lower())
        self.assertIn("animation factory boom", result.detail)
        self.assertTrue(ExplodingAnimationFactory.called)

    def test_startup_via_motor_bus_waits_for_completion(self) -> None:
        # Proxy branch must not return success until wait_until_playback_complete
        # signals done, otherwise dashboard busy lock releases mid-choreography
        # and the next click shears the state machine.
        settings = self._make_settings()
        fake_sentinel = SimpleNamespace(
            pid=1, port=0, base_url="http://127.0.0.1:0", started_at_ms=0
        )

        bridge = DashboardRuntimeBridge(
            settings,
            animation_factory=FakeAnimationService,
            rgb_factory=FakeRGBService,
            remote_module=SimpleNamespace(),
        )

        with patch.object(runtime_bridge_mod, "current_sentinel", return_value=fake_sentinel):
            FakeAnimationService.wait_result = True
            result = bridge.startup()

        self.assertTrue(result.ok)
        service = FakeAnimationService.instances[-1]
        self.assertEqual(service.dispatched, [("startup", "wake_up")])

    def test_startup_via_motor_bus_reports_timeout_when_wait_returns_false(self) -> None:
        settings = self._make_settings()
        fake_sentinel = SimpleNamespace(
            pid=1, port=0, base_url="http://127.0.0.1:0", started_at_ms=0
        )

        bridge = DashboardRuntimeBridge(
            settings,
            animation_factory=FakeAnimationService,
            rgb_factory=FakeRGBService,
            remote_module=SimpleNamespace(),
        )

        with patch.object(runtime_bridge_mod, "current_sentinel", return_value=fake_sentinel):
            FakeAnimationService.wait_result = False
            result = bridge.startup()

        self.assertFalse(result.ok)
        self.assertIn("timed out", result.message.lower())
        self.assertEqual(result.detail, "wake_up")

    def test_startup_converts_remote_exception_to_failed_result(self) -> None:
        settings = self._make_settings()

        remote_module = SimpleNamespace(
            _handle_startup=lambda args: (_ for _ in ()).throw(RuntimeError("remote crashed")),
            DEFAULT_STARTUP_SETTLE_FRAMES=18,
            DEFAULT_STARTUP_HOLD_FRAMES=10,
            DEFAULT_STARTUP_FPS=15,
            DEFAULT_WAKE_FPS=30,
            DEFAULT_POST_WAKE_HOLD_SECONDS=0.8,
        )

        bridge = DashboardRuntimeBridge(
            settings,
            animation_factory=FakeAnimationService,
            rgb_factory=FakeRGBService,
            remote_module=remote_module,
        )

        result = bridge.startup()

        self.assertFalse(result.ok)
        self.assertIn("failed", result.message.lower())
        self.assertIn("remote crashed", result.detail)

    def test_set_light_solid_dispatches_rgb_event_and_keeps_state(self) -> None:
        settings = self._make_settings()

        bridge = DashboardRuntimeBridge(
            settings,
            animation_factory=FakeAnimationService,
            rgb_factory=FakeRGBService,
            remote_module=SimpleNamespace(),
        )

        result = bridge.set_light_solid((255, 170, 70))

        self.assertTrue(result.ok)
        self.assertEqual(FakeRGBService.instances[-1].actions, [("solid", (255, 170, 70))])

    def test_set_light_solid_returns_failed_result_when_rgb_disabled(self) -> None:
        settings = self._make_settings(enable_rgb=False)

        bridge = DashboardRuntimeBridge(
            settings,
            animation_factory=FakeAnimationService,
            rgb_factory=ExplodingFactory,
            remote_module=SimpleNamespace(),
        )

        result = bridge.set_light_solid((255, 170, 70))

        self.assertFalse(result.ok)
        self.assertIn("disabled", result.message.lower())
        self.assertFalse(ExplodingFactory.called)

    def test_clear_light_returns_failed_result_when_rgb_disabled(self) -> None:
        settings = self._make_settings(enable_rgb=False)

        bridge = DashboardRuntimeBridge(
            settings,
            animation_factory=FakeAnimationService,
            rgb_factory=ExplodingFactory,
            remote_module=SimpleNamespace(),
        )

        result = bridge.clear_light()

        self.assertFalse(result.ok)
        self.assertIn("disabled", result.message.lower())
        self.assertFalse(ExplodingFactory.called)

    def test_clear_light_converts_rgb_service_exception_to_failed_result(self) -> None:
        settings = self._make_settings(enable_rgb=True)
        FakeRGBService.raise_on_clear = RuntimeError("device missing")

        bridge = DashboardRuntimeBridge(
            settings,
            animation_factory=FakeAnimationService,
            rgb_factory=FakeRGBService,
            remote_module=SimpleNamespace(),
        )

        result = bridge.clear_light()

        self.assertFalse(result.ok)
        self.assertIn("failed", result.message.lower())
        self.assertIn("device missing", result.detail)


if __name__ == "__main__":
    unittest.main()
