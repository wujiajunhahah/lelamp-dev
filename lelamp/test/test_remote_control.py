import os
import socket
import sys
import tempfile
import threading
import time
import types
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

if "livekit.plugins" not in sys.modules:
    fake_livekit = types.ModuleType("livekit")
    fake_plugins = types.ModuleType("livekit.plugins")
    fake_plugins.openai = object()
    fake_livekit.plugins = fake_plugins
    sys.modules["livekit"] = fake_livekit
    sys.modules["livekit.plugins"] = fake_plugins


def _pick_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class _LiveServer:
    """Run uvicorn on a fixed port in a daemon thread for proxy tests."""

    def __init__(self, app, port: int) -> None:
        import uvicorn

        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            lifespan="off",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def __enter__(self) -> "_LiveServer":
        self._thread.start()
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if getattr(self._server, "started", False):
                return self
            time.sleep(0.05)
        raise RuntimeError("test server failed to start")

    def __exit__(self, *exc_info) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=3.0)


class _sentinel_ctx:
    """Context manager that writes a sentinel into a test-specific path and cleans up."""

    def __init__(self, sentinel_mod, info) -> None:
        self._sentinel_mod = sentinel_mod
        self._info = info
        self._path = Path(
            os.environ.get("TMPDIR", "/tmp")
        ) / f"lelamp-motor-bus-remote-test-{os.getpid()}.json"
        self._env_patcher = patch.dict(
            os.environ, {"LELAMP_MOTOR_BUS_SENTINEL": str(self._path)}
        )

    def __enter__(self):
        self._env_patcher.start()
        self._sentinel_mod.write_sentinel(self._info)
        return self

    def __exit__(self, *exc_info):
        self._sentinel_mod.remove_sentinel()
        self._env_patcher.stop()


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

    def test_handle_solid_routes_via_rgb_proxy_when_agent_alive(self) -> None:
        with patch.dict(sys.modules, _fake_runtime_modules(), clear=False):
            sys.modules.pop("lelamp.remote_control", None)
            from lelamp import remote_control

        from fastapi import FastAPI  # noqa: F401 (imported inside guarded block below)

        from lelamp.motor_bus import sentinel as sentinel_mod
        from lelamp.motor_bus.server import build_app

        class _FakeRGB:
            def __init__(self) -> None:
                self.dispatched: list[tuple[str, Any]] = []
                self.cleared = False

            def dispatch(self, event_type: str, payload: Any) -> None:
                self.dispatched.append((event_type, payload))

            def clear(self) -> None:
                self.cleared = True

        rgb = _FakeRGB()
        app = build_app(
            animation_service=SimpleNamespace(
                get_available_recordings=lambda: [],
                dispatch=lambda *_: None,
                wait_until_playback_complete=lambda timeout=None: True,
            ),
            get_animation_service_error=lambda: None,
            rgb_service=rgb,
            led_count=40,
        )

        port = _pick_free_port()
        base_url = f"http://127.0.0.1:{port}"
        with _LiveServer(app, port) as _srv, _sentinel_ctx(
            sentinel_mod,
            sentinel_mod.SentinelInfo(
                pid=os.getpid(),
                port=port,
                base_url=base_url,
                started_at_ms=1,
            ),
        ):
            def _fail_direct() -> None:
                raise AssertionError(
                    "direct RGBService factory should not fire while proxy is reachable"
                )

            with patch.object(remote_control, "_build_rgb_service", side_effect=_fail_direct):
                args = SimpleNamespace(
                    enable_rgb=True, red=10, green=20, blue=30,
                )
                self.assertEqual(remote_control._handle_solid(args), 0)

                args_clear = SimpleNamespace(enable_rgb=True)
                self.assertEqual(remote_control._handle_clear(args_clear), 0)

        self.assertEqual(rgb.dispatched, [("solid", (10, 20, 30))])
        self.assertTrue(rgb.cleared)

    def test_handle_startup_refuses_when_agent_motor_live(self) -> None:
        with patch.dict(sys.modules, _fake_runtime_modules(include_follower=True), clear=False):
            sys.modules.pop("lelamp.remote_control", None)
            from lelamp import remote_control

        fake_sentinel = SimpleNamespace(
            pid=os.getpid(),
            port=8770,
            base_url="http://127.0.0.1:8770",
            started_at_ms=1,
        )
        args = SimpleNamespace(
            recording="wake_up",
            home_recording="home_safe",
            port="/dev/ttyACM0",
            id="lelamp",
            enable_rgb=False,
            settle_frames=0,
            settle_hold_frames=0,
            settle_fps=30,
            wake_fps=30,
            post_wake_hold=0.0,
            led_count=40,
            led_pin=12,
            led_freq_hz=800000,
            led_dma=10,
            led_brightness=255,
            led_invert=False,
            led_channel=0,
        )
        with patch.object(
            remote_control,
            "current_sentinel",
            return_value=fake_sentinel,
        ) as spy:
            self.assertEqual(remote_control._handle_startup(args), 2)
            # Must probe the motor domain, not generic "any"; otherwise an
            # agent that failed to acquire the bus would still get refused.
            spy.assert_called_once_with(require=remote_control.REQUIRE_MOTOR)

    def test_handle_shutdown_refuses_when_agent_motor_live(self) -> None:
        with patch.dict(sys.modules, _fake_runtime_modules(include_follower=True), clear=False):
            sys.modules.pop("lelamp.remote_control", None)
            from lelamp import remote_control

        fake_sentinel = SimpleNamespace(
            pid=os.getpid(),
            port=8770,
            base_url="http://127.0.0.1:8770",
            started_at_ms=1,
        )
        args = SimpleNamespace(
            recording="power_off",
            port="/dev/ttyACM0",
            id="lelamp",
            fps=30,
        )
        with patch.object(
            remote_control,
            "current_sentinel",
            return_value=fake_sentinel,
        ) as spy:
            self.assertEqual(remote_control._handle_shutdown(args), 2)
            spy.assert_called_once_with(require=remote_control.REQUIRE_MOTOR)

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
