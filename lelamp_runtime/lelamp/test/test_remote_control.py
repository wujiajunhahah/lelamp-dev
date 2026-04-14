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
        fake_animation_module = types.ModuleType("lelamp.service.motors.animation_service")
        fake_animation_module.AnimationService = object
        fake_rgb_module = types.ModuleType("lelamp.service.rgb.rgb_service")
        fake_rgb_module.RGBService = object

        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(tmp_dir, ".env").write_text("LELAMP_LED_COUNT=64\nLELAMP_LED_PIN=18\n", encoding="utf-8")

            with patch.dict(
                sys.modules,
                {
                    "lelamp.service.motors.motors_service": fake_motors_module,
                    "lelamp.service.motors.animation_service": fake_animation_module,
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
        fake_animation_module = types.ModuleType("lelamp.service.motors.animation_service")
        fake_animation_module.AnimationService = object
        fake_rgb_module = types.ModuleType("lelamp.service.rgb.rgb_service")
        fake_rgb_module.RGBService = object
        fake_follower_module = types.ModuleType("lelamp.follower")
        fake_follower_module.LeLampFollower = object
        fake_follower_module.LeLampFollowerConfig = object

        with patch.dict(
            sys.modules,
            {
                "lelamp.service.motors.motors_service": fake_motors_module,
                "lelamp.service.motors.animation_service": fake_animation_module,
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

    def test_handle_capture_pose_set_defaults_updates_idle_and_home_only(self) -> None:
        class FakeBus:
            def __init__(self) -> None:
                self.is_connected = False

            def connect(self) -> None:
                self.is_connected = True

            def sync_read(self, *_args, **_kwargs):
                return {
                    "base_yaw": 3.071017,
                    "base_pitch": 30.995671,
                    "elbow_pitch": 32.141337,
                    "wrist_roll": 96.923077,
                    "wrist_pitch": 70.990468,
                }

            def disconnect(self, disable_torque=False) -> None:
                self.is_connected = False

        class FakeFollower:
            def __init__(self, _config) -> None:
                self.bus = FakeBus()

        class FakeFollowerConfig:
            def __init__(self, **kwargs) -> None:
                self.kwargs = kwargs

        from lelamp import remote_control

        fake_follower_module = types.ModuleType("lelamp.follower")
        fake_follower_module.LeLampFollower = FakeFollower
        fake_follower_module.LeLampFollowerConfig = FakeFollowerConfig

        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(
            sys.modules,
            {"lelamp.follower": fake_follower_module},
            clear=False,
        ), patch.object(remote_control, "write_static_recording", return_value=Path(tmp_dir, "home_safe.csv")):
            env_path = Path(tmp_dir, ".env")
            env_path.write_text(
                "\n".join(
                    [
                        "LELAMP_STARTUP_RECORDING=wake_up",
                        "LELAMP_IDLE_RECORDING=idle",
                        "LELAMP_HOME_RECORDING=idle",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                port="/dev/ttyACM0",
                id="lelamp",
                fps=30,
                frame_count=3,
                name="home_safe",
                env_file=str(env_path),
                set_defaults=True,
            )

            result = remote_control._handle_capture_pose(args)
            env_contents = env_path.read_text(encoding="utf-8")

        self.assertEqual(result, 0)
        self.assertEqual(
            env_contents,
            "\n".join(
                [
                    "LELAMP_STARTUP_RECORDING=wake_up",
                    "LELAMP_IDLE_RECORDING=home_safe",
                    "LELAMP_HOME_RECORDING=home_safe",
                    "LELAMP_USE_HOME_POSE_RELATIVE=true",
                    "",
                ]
            ),
        )

    def test_build_parser_supports_startup_and_shutdown_commands(self) -> None:
        fake_motors_module = types.ModuleType("lelamp.service.motors.motors_service")
        fake_motors_module.MotorsService = object
        fake_animation_module = types.ModuleType("lelamp.service.motors.animation_service")
        fake_animation_module.AnimationService = object
        fake_rgb_module = types.ModuleType("lelamp.service.rgb.rgb_service")
        fake_rgb_module.RGBService = object

        with patch.dict(
            sys.modules,
            {
                "lelamp.service.motors.motors_service": fake_motors_module,
                "lelamp.service.motors.animation_service": fake_animation_module,
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

    def test_handle_startup_continues_when_rgb_init_fails(self) -> None:
        class FakeBus:
            def __init__(self) -> None:
                self.is_connected = True

            def sync_read(self, *_args, **_kwargs):
                return {
                    "base_yaw": 1.0,
                    "base_pitch": 2.0,
                    "elbow_pitch": 3.0,
                    "wrist_roll": 4.0,
                    "wrist_pitch": 5.0,
                }

            def write(self, *_args, **_kwargs) -> None:
                return None

        class FakeFollower:
            instances: list["FakeFollower"] = []

            def __init__(self, _config) -> None:
                self.bus = FakeBus()
                self.is_connected = False
                self.actions = []
                FakeFollower.instances.append(self)

            def connect(self, calibrate=False) -> None:
                self.is_connected = True

            def send_action(self, action) -> None:
                self.actions.append(action)

            def disconnect(self) -> None:
                self.is_connected = False

        class FakeFollowerConfig:
            def __init__(self, **kwargs) -> None:
                self.kwargs = kwargs

        class FakeRgbInitError(RuntimeError):
            pass

        from lelamp import remote_control

        args = SimpleNamespace(
            port="/dev/ttyACM0",
            id="lelamp",
            recording="wake_up",
            home_recording="home_safe",
            settle_frames=1,
            settle_hold_frames=1,
            return_frames=1,
            final_hold_frames=1,
            settle_fps=15,
            wake_fps=30,
            post_wake_hold=0.0,
            enable_rgb=True,
            led_count=40,
            led_pin=12,
            led_freq_hz=800000,
            led_dma=10,
            led_brightness=255,
            led_invert=False,
            led_channel=0,
        )

        fake_follower_module = types.ModuleType("lelamp.follower")
        fake_follower_module.LeLampFollower = FakeFollower
        fake_follower_module.LeLampFollowerConfig = FakeFollowerConfig

        with patch.dict(sys.modules, {"lelamp.follower": fake_follower_module}, clear=False), patch.object(
            remote_control,
            "_build_rgb_service",
            side_effect=FakeRgbInitError("rgb boom"),
        ), patch.object(
            remote_control,
            "_load_first_pose",
            return_value={"base_yaw.pos": 1.0, "base_pitch.pos": 2.0, "elbow_pitch.pos": 3.0, "wrist_roll.pos": 4.0, "wrist_pitch.pos": 5.0},
        ), patch.object(
            remote_control,
            "_load_recording_actions",
            return_value=[
                {"base_yaw.pos": 1.0, "base_pitch.pos": 2.0, "elbow_pitch.pos": 3.0, "wrist_roll.pos": 4.0, "wrist_pitch.pos": 5.0},
                {"base_yaw.pos": 2.0, "base_pitch.pos": 3.0, "elbow_pitch.pos": 4.0, "wrist_roll.pos": 5.0, "wrist_pitch.pos": 6.0},
            ],
        ), patch.object(remote_control.time, "sleep", return_value=None):
            result = remote_control._handle_startup(args)

        self.assertEqual(result, 0)
        self.assertTrue(FakeFollower.instances)
        self.assertTrue(FakeFollower.instances[0].actions)


if __name__ == "__main__":
    unittest.main()
