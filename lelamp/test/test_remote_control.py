import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

if "livekit.plugins" not in sys.modules:
    fake_livekit = types.ModuleType("livekit")
    fake_plugins = types.ModuleType("livekit.plugins")
    fake_plugins.openai = object()
    fake_livekit.plugins = fake_plugins
    sys.modules["livekit"] = fake_livekit
    sys.modules["livekit.plugins"] = fake_plugins


def _fake_runtime_modules(include_follower: bool = False) -> dict[str, types.ModuleType]:
    fake_motors_module = types.ModuleType("lelamp.service.motors.motors_service")
    fake_motors_module.MotorsService = object
    fake_animation_module = types.ModuleType("lelamp.service.motors.animation_service")
    fake_animation_module.AnimationService = object
    fake_rgb_module = types.ModuleType("lelamp.service.rgb.rgb_service")
    fake_rgb_module.RGBService = object

    modules = {
        "lelamp.service.motors.motors_service": fake_motors_module,
        "lelamp.service.motors.animation_service": fake_animation_module,
        "lelamp.service.rgb.rgb_service": fake_rgb_module,
    }
    if include_follower:
        fake_follower_module = types.ModuleType("lelamp.follower")
        fake_follower_module.LeLampFollower = object
        fake_follower_module.LeLampFollowerConfig = object
        modules["lelamp.follower"] = fake_follower_module
    return modules


class RemoteControlConfigTests(unittest.TestCase):
    def test_build_parser_loads_led_defaults_from_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(tmp_dir, ".env").write_text("LELAMP_LED_COUNT=64\nLELAMP_LED_PIN=18\n", encoding="utf-8")

            with patch.dict(
                sys.modules,
                _fake_runtime_modules(),
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
        with patch.dict(
            sys.modules,
            _fake_runtime_modules(include_follower=True),
            clear=False,
        ):
            sys.modules.pop("lelamp.remote_control", None)
            from lelamp import remote_control

            parser = remote_control.build_parser()
            args = parser.parse_args(["capture-pose", "home_safe", "--set-defaults"])

        self.assertEqual(args.name, "home_safe")
        self.assertTrue(args.set_defaults)

    def test_build_parser_supports_startup_and_shutdown_commands(self) -> None:
        with patch.dict(
            sys.modules,
            _fake_runtime_modules(),
            clear=False,
        ):
            sys.modules.pop("lelamp.remote_control", None)
            from lelamp import remote_control

            parser = remote_control.build_parser()
            startup_args = parser.parse_args(["startup"])
            shutdown_args = parser.parse_args(["shutdown"])

        self.assertEqual(startup_args.command, "startup")
        self.assertEqual(shutdown_args.command, "shutdown")

    def test_build_parser_supports_sync_pose_recordings_command(self) -> None:
        with patch.dict(
            sys.modules,
            _fake_runtime_modules(),
            clear=False,
        ):
            sys.modules.pop("lelamp.remote_control", None)
            from lelamp import remote_control

            parser = remote_control.build_parser()
            args = parser.parse_args(["sync-pose-recordings", "--set-defaults"])

        self.assertEqual(args.command, "sync-pose-recordings")
        self.assertTrue(args.set_defaults)

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

        with patch.dict(sys.modules, _fake_runtime_modules(), clear=False):
            sys.modules.pop("lelamp.remote_control", None)
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

    def test_handle_sync_pose_recordings_writes_default_pose_files_and_env(self) -> None:
        with patch.dict(sys.modules, _fake_runtime_modules(), clear=False):
            sys.modules.pop("lelamp.remote_control", None)
            from lelamp import remote_control

        with tempfile.TemporaryDirectory() as tmp_dir:
            recording_dir = Path(tmp_dir) / "recordings"
            env_path = Path(tmp_dir) / ".env"
            args = SimpleNamespace(
                fps=24,
                frame_count=3,
                env_file=str(env_path),
                set_defaults=True,
            )

            with patch.object(remote_control, "_recordings_dir", return_value=recording_dir):
                result = remote_control._handle_sync_pose_recordings(args)

            self.assertEqual(result, 0)
            self.assertTrue((recording_dir / "home_safe.csv").exists())
            self.assertTrue((recording_dir / "sleep_pose.csv").exists())
            self.assertTrue((recording_dir / "power_off.csv").exists())
            env_content = env_path.read_text(encoding="utf-8")
            self.assertIn("LELAMP_IDLE_RECORDING=home_safe", env_content)
            self.assertIn("LELAMP_HOME_RECORDING=home_safe", env_content)
            self.assertIn("LELAMP_USE_HOME_POSE_RELATIVE=true", env_content)


if __name__ == "__main__":
    unittest.main()
