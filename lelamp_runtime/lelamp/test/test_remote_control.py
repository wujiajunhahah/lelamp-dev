import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

class RemoteControlConfigTests(unittest.TestCase):
    def test_build_parser_loads_led_defaults_from_dotenv(self) -> None:
        fake_motors_module = types.ModuleType("lelamp.service.motors.motors_service")
        fake_motors_module.MotorsService = object
        fake_rgb_module = types.ModuleType("lelamp.service.rgb.rgb_service")
        fake_rgb_module.RGBService = object

        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(tmp_dir, ".env").write_text("LELAMP_LED_COUNT=64\nLELAMP_LED_PIN=18\n", encoding="utf-8")

            with patch.dict(
                sys.modules,
                {
                    "lelamp.service.motors.motors_service": fake_motors_module,
                    "lelamp.service.rgb.rgb_service": fake_rgb_module,
                },
                clear=False,
            ), patch.dict(os.environ, {}, clear=True):
                previous_cwd = os.getcwd()
                try:
                    os.chdir(tmp_dir)
                    sys.modules.pop("lelamp.remote_control", None)
                    from lelamp import remote_control

                    parser = remote_control.build_parser()
                    args = parser.parse_args(["show-config"])
                finally:
                    os.chdir(previous_cwd)

            self.assertEqual(args.led_count, 64)
            self.assertEqual(args.led_pin, 18)

    def test_build_parser_supports_capture_pose_command(self) -> None:
        fake_motors_module = types.ModuleType("lelamp.service.motors.motors_service")
        fake_motors_module.MotorsService = object
        fake_rgb_module = types.ModuleType("lelamp.service.rgb.rgb_service")
        fake_rgb_module.RGBService = object
        fake_follower_module = types.ModuleType("lelamp.follower")
        fake_follower_module.LeLampFollower = object
        fake_follower_module.LeLampFollowerConfig = object

        with patch.dict(
            sys.modules,
            {
                "lelamp.service.motors.motors_service": fake_motors_module,
                "lelamp.service.rgb.rgb_service": fake_rgb_module,
                "lelamp.follower": fake_follower_module,
            },
            clear=False,
        ):
            sys.modules.pop("lelamp.remote_control", None)
            from lelamp import remote_control

            parser = remote_control.build_parser()
            args = parser.parse_args(["capture-pose", "home_safe", "--set-defaults"])

        self.assertEqual(args.name, "home_safe")
        self.assertTrue(args.set_defaults)

    def test_build_parser_supports_startup_and_shutdown_commands(self) -> None:
        fake_motors_module = types.ModuleType("lelamp.service.motors.motors_service")
        fake_motors_module.MotorsService = object
        fake_rgb_module = types.ModuleType("lelamp.service.rgb.rgb_service")
        fake_rgb_module.RGBService = object

        with patch.dict(
            sys.modules,
            {
                "lelamp.service.motors.motors_service": fake_motors_module,
                "lelamp.service.rgb.rgb_service": fake_rgb_module,
            },
            clear=False,
        ):
            sys.modules.pop("lelamp.remote_control", None)
            from lelamp import remote_control

            parser = remote_control.build_parser()
            startup_args = parser.parse_args(["startup"])
            shutdown_args = parser.parse_args(["shutdown"])

        self.assertEqual(startup_args.command, "startup")
        self.assertEqual(shutdown_args.command, "shutdown")

    def test_handle_play_uses_animation_service_for_reanchored_playback(self) -> None:
        class UnexpectedMotorsService:
            def __init__(self, *args, **kwargs) -> None:
                raise AssertionError("MotorsService should not be used for remote_control play")

        class FakeAnimationService:
            instances: list["FakeAnimationService"] = []

            def __init__(self, *args, **kwargs) -> None:
                self.args = args
                self.kwargs = kwargs
                self.started = False
                self.dispatched: list[tuple[str, str]] = []
                self.stopped = False
                self.wait_timeout = None
                FakeAnimationService.instances.append(self)

            def get_available_recordings(self) -> list[str]:
                return ["curious"]

            def start(self) -> None:
                self.started = True

            def dispatch(self, event_type: str, payload: str) -> None:
                self.dispatched.append((event_type, payload))

            def wait_until_playback_complete(self, timeout: float | None = None) -> bool:
                self.wait_timeout = timeout
                return True

            def stop(self) -> None:
                self.stopped = True

        from lelamp import remote_control

        fake_settings = SimpleNamespace(
            interpolation_duration=3.0,
            idle_recording="home_safe",
            home_recording="home_safe",
            use_home_pose_relative=True,
        )

        with patch.object(remote_control, "AnimationService", FakeAnimationService), patch.object(
            remote_control,
            "MotorsService",
            UnexpectedMotorsService,
        ), patch.object(remote_control, "load_runtime_settings", return_value=fake_settings):
            args = SimpleNamespace(
                name="curious",
                port="/dev/ttyACM0",
                id="lelamp",
                fps=30,
                timeout=12.0,
            )

            result = remote_control._handle_play(args)

        self.assertEqual(result, 0)
        self.assertEqual(len(FakeAnimationService.instances), 1)
        service = FakeAnimationService.instances[0]
        self.assertTrue(service.started)
        self.assertEqual(service.dispatched, [("play", "curious")])
        self.assertEqual(service.wait_timeout, 12.0)
        self.assertTrue(service.stopped)


if __name__ == "__main__":
    unittest.main()
