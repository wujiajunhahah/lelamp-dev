import unittest
from types import SimpleNamespace

from lelamp.dashboard.runtime_bridge import DashboardRuntimeBridge


class FakeAnimationService:
    instances = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.started = False
        self.dispatched = []
        self.stopped = False
        FakeAnimationService.instances.append(self)

    def get_available_recordings(self) -> list[str]:
        return ["curious", "wake_up"]

    def start(self) -> None:
        self.started = True

    def dispatch(self, event_type: str, payload: str) -> None:
        self.dispatched.append((event_type, payload))

    def wait_until_playback_complete(self, timeout: float | None = None) -> bool:
        return True

    def stop(self) -> None:
        self.stopped = True


class FakeRGBService:
    instances = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.actions = []
        FakeRGBService.instances.append(self)

    def handle_event(self, event_type: str, payload) -> None:
        self.actions.append((event_type, payload))

    def clear(self) -> None:
        self.actions.append(("clear", None))

    def stop(self) -> None:
        self.actions.append(("stop", None))


class DashboardRuntimeBridgeTests(unittest.TestCase):
    def test_play_uses_home_recording_as_idle_target(self) -> None:
        settings = SimpleNamespace(
            port="/dev/ttyACM0",
            lamp_id="lelamp",
            fps=30,
            interpolation_duration=3.0,
            startup_recording="wake_up",
            home_recording="home_safe",
            use_home_pose_relative=True,
            enable_rgb=True,
            led_count=40,
            led_pin=12,
            led_freq_hz=800000,
            led_dma=10,
            led_brightness=255,
            led_invert=False,
            led_channel=0,
        )

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

    def test_set_light_solid_dispatches_rgb_event(self) -> None:
        settings = SimpleNamespace(
            port="/dev/ttyACM0",
            lamp_id="lelamp",
            fps=30,
            interpolation_duration=3.0,
            startup_recording="wake_up",
            home_recording="home_safe",
            use_home_pose_relative=True,
            enable_rgb=True,
            led_count=40,
            led_pin=12,
            led_freq_hz=800000,
            led_dma=10,
            led_brightness=255,
            led_invert=False,
            led_channel=0,
        )

        bridge = DashboardRuntimeBridge(
            settings,
            animation_factory=FakeAnimationService,
            rgb_factory=FakeRGBService,
            remote_module=SimpleNamespace(),
        )

        result = bridge.set_light_solid((255, 170, 70))

        self.assertTrue(result.ok)
        self.assertEqual(FakeRGBService.instances[-1].actions[0], ("solid", (255, 170, 70)))


if __name__ == "__main__":
    unittest.main()
