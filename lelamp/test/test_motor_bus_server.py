import threading
import time
import unittest
from typing import Any
from unittest import mock

from fastapi.testclient import TestClient

from lelamp.motor_bus.server import build_app


class FakeAnimationService:
    def __init__(self, recordings: list[str] | None = None) -> None:
        self.recordings = recordings or ["wake_up", "home_safe", "power_off"]
        self.dispatched: list[tuple[str, Any]] = []
        # Matches the real AnimationService attribute name so the server's
        # pre-dispatch gate (server.py::_arm_playback_gate) reaches into it.
        self._playback_done = threading.Event()
        self._playback_done.set()

    # Convenience alias kept for tests that speak begin/end semantics.
    @property
    def _done(self) -> threading.Event:
        return self._playback_done

    def get_available_recordings(self) -> list[str]:
        return list(self.recordings)

    def dispatch(self, event_type: str, payload: Any) -> None:
        self.dispatched.append((event_type, payload))

    def begin_playback(self) -> None:
        self._playback_done.clear()

    def end_playback(self) -> None:
        self._playback_done.set()

    def wait_until_playback_complete(self, timeout: float | None = None) -> bool:
        return self._playback_done.wait(timeout=timeout)


class FakeRGBService:
    def __init__(self) -> None:
        self.dispatched: list[tuple[str, Any]] = []
        self.cleared = False

    def dispatch(self, event_type: str, payload: Any) -> None:
        self.dispatched.append((event_type, payload))

    def clear(self) -> None:
        self.cleared = True


def _build_client(
    *,
    animation: FakeAnimationService | None = None,
    rgb: FakeRGBService | None = None,
    animation_error: str | None = None,
    led_count: int = 40,
) -> tuple[TestClient, FakeAnimationService, FakeRGBService | None]:
    animation = animation or FakeAnimationService()
    app = build_app(
        animation_service=animation,
        get_animation_service_error=lambda: animation_error,
        rgb_service=rgb,
        led_count=led_count,
    )
    return TestClient(app), animation, rgb


class MotorBusServerTests(unittest.TestCase):
    def test_health_reports_domain_flags_when_all_ok(self) -> None:
        rgb = FakeRGBService()
        client, _, _ = _build_client(rgb=rgb, led_count=40)
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["motor_ok"])
        self.assertTrue(body["rgb_ok"])
        self.assertTrue(body["rgb_available"])  # legacy field retained
        self.assertEqual(body["led_count"], 40)
        self.assertIsNone(body["animation_error"])

    def test_health_motor_ok_false_when_animation_errored(self) -> None:
        client, _, _ = _build_client(animation_error="/dev/ttyACM0 missing")
        body = client.get("/health").json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["motor_ok"])
        self.assertEqual(body["animation_error"], "/dev/ttyACM0 missing")

    def test_health_rgb_ok_false_when_rgb_disabled(self) -> None:
        client, _, _ = _build_client(rgb=None)
        body = client.get("/health").json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["rgb_ok"])
        self.assertFalse(body["rgb_available"])

    def test_recordings_endpoint(self) -> None:
        animation = FakeAnimationService(recordings=["curious", "wake_up"])
        client, _, _ = _build_client(animation=animation)
        resp = client.get("/motor/recordings")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"recordings": ["curious", "wake_up"]})

    def test_play_dispatches_event(self) -> None:
        client, animation, _ = _build_client()
        resp = client.post("/motor/play", json={"recording_name": "wake_up"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(animation.dispatched, [("play", "wake_up")])

    def test_play_blocked_when_animation_errored(self) -> None:
        client, _, _ = _build_client(animation_error="/dev/ttyACM0 missing")
        resp = client.post("/motor/play", json={"recording_name": "wake_up"})
        self.assertEqual(resp.status_code, 503)
        self.assertIn("motion unavailable", resp.json()["detail"])

    def test_startup_dispatches_event(self) -> None:
        client, animation, _ = _build_client()
        resp = client.post("/motor/startup", json={"recording_name": "wake_up"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(animation.dispatched, [("startup", "wake_up")])

    def test_rgb_solid_dispatches(self) -> None:
        rgb = FakeRGBService()
        client, _, _ = _build_client(rgb=rgb)
        resp = client.post("/rgb/solid", json={"red": 255, "green": 170, "blue": 70})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(rgb.dispatched, [("solid", (255, 170, 70))])

    def test_rgb_solid_rejects_out_of_range(self) -> None:
        rgb = FakeRGBService()
        client, _, _ = _build_client(rgb=rgb)
        resp = client.post("/rgb/solid", json={"red": 256, "green": 0, "blue": 0})
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(rgb.dispatched, [])

    def test_rgb_paint_validates_colors(self) -> None:
        rgb = FakeRGBService()
        client, _, _ = _build_client(rgb=rgb)
        resp = client.post("/rgb/paint", json={"colors": [[255, 0, 0], [0, 256, 0]]})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(rgb.dispatched, [])

    def test_rgb_paint_happy_path(self) -> None:
        rgb = FakeRGBService()
        client, _, _ = _build_client(rgb=rgb)
        resp = client.post("/rgb/paint", json={"colors": [[255, 0, 0], [0, 255, 0]]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(rgb.dispatched, [("paint", [(255, 0, 0), (0, 255, 0)])])

    def test_rgb_clear_calls_service(self) -> None:
        rgb = FakeRGBService()
        client, _, _ = _build_client(rgb=rgb)
        resp = client.post("/rgb/clear")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(rgb.cleared)

    def test_rgb_endpoints_503_when_disabled(self) -> None:
        client, _, _ = _build_client(rgb=None)
        for path, body in [
            ("/rgb/solid", {"red": 1, "green": 2, "blue": 3}),
            ("/rgb/paint", {"colors": [[1, 2, 3]]}),
            ("/rgb/clear", None),
        ]:
            with self.subTest(path=path):
                resp = client.post(path, json=body)
                self.assertEqual(resp.status_code, 503)

    def test_wait_complete_returns_done_when_animation_finishes(self) -> None:
        animation = FakeAnimationService()
        animation.begin_playback()
        client, _, _ = _build_client(animation=animation)

        def _finish_soon() -> None:
            time.sleep(0.1)
            animation.end_playback()

        threading.Thread(target=_finish_soon, daemon=True).start()
        resp = client.post("/motor/wait_complete", json={"timeout": 2.0})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["done"])
        self.assertEqual(body["timeout"], 2.0)

    def test_wait_complete_reports_false_on_timeout(self) -> None:
        animation = FakeAnimationService()
        animation.begin_playback()  # never finishes
        client, _, _ = _build_client(animation=animation)
        resp = client.post("/motor/wait_complete", json={"timeout": 0.1})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["done"])

    def test_wait_complete_503_when_animation_errored(self) -> None:
        client, _, _ = _build_client(animation_error="serial busy")
        resp = client.post("/motor/wait_complete", json={"timeout": 0.1})
        self.assertEqual(resp.status_code, 503)

    def test_wait_complete_rejects_oversize_timeout(self) -> None:
        client, _, _ = _build_client()
        resp = client.post("/motor/wait_complete", json={"timeout": 999.0})
        # pydantic Field(le=180.0) rejects with 422.
        self.assertEqual(resp.status_code, 422)

    def test_play_pre_clears_playback_done_gate(self) -> None:
        # Regression guard for the race exposed on Pi: without pre-clearing the
        # completion event inside /motor/play the subsequent /motor/wait_complete
        # observed the previous done=True state and returned immediately, letting
        # the dashboard busy lock release before the real playback had started.
        animation = FakeAnimationService()
        self.assertTrue(animation._playback_done.is_set())
        client, _, _ = _build_client(animation=animation)
        resp = client.post("/motor/play", json={"recording_name": "wake_up"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            animation._playback_done.is_set(),
            "play endpoint must arm the completion gate before event_loop picks up the event",
        )

    def test_startup_pre_clears_playback_done_gate(self) -> None:
        animation = FakeAnimationService()
        self.assertTrue(animation._playback_done.is_set())
        client, _, _ = _build_client(animation=animation)
        resp = client.post("/motor/startup", json={"recording_name": "wake_up"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(animation._playback_done.is_set())


class MotorBusServerBindRetryTests(unittest.TestCase):
    def test_start_retries_bind_until_port_frees(self) -> None:
        from lelamp.motor_bus import server as server_module

        busy_iterations = [False, False, True]  # free on 3rd probe

        def fake_port_is_free(host: str, port: int) -> bool:
            return busy_iterations.pop(0)

        bus = server_module.MotorBusServer(
            animation_service=FakeAnimationService(),
            get_animation_service_error=lambda: None,
            rgb_service=None,
            led_count=40,
        )

        with mock.patch.object(server_module, "_port_is_free", side_effect=fake_port_is_free), \
             mock.patch.object(server_module.time, "sleep"), \
             mock.patch.object(server_module, "write_sentinel") as write_sentinel, \
             mock.patch("uvicorn.Config"), \
             mock.patch("uvicorn.Server") as FakeServer, \
             mock.patch.object(server_module.threading, "Thread") as FakeThread:
            fake_server = mock.Mock()
            fake_server.started = True
            FakeServer.return_value = fake_server
            FakeThread.return_value = mock.Mock()

            bus.start(ready_timeout=0.2, bind_retry_total_s=5.0, bind_retry_interval_s=0.01)

            self.assertEqual(busy_iterations, [])
            self.assertTrue(bus.is_ready())
            write_sentinel.assert_called_once()

    def test_start_gives_up_after_retry_deadline(self) -> None:
        from lelamp.motor_bus import server as server_module

        bus = server_module.MotorBusServer(
            animation_service=FakeAnimationService(),
            get_animation_service_error=lambda: None,
            rgb_service=None,
            led_count=40,
        )

        with mock.patch.object(server_module, "_port_is_free", return_value=False), \
             mock.patch.object(server_module.time, "sleep"), \
             mock.patch.object(server_module, "write_sentinel") as write_sentinel:
            bus.start(ready_timeout=0.2, bind_retry_total_s=0.0, bind_retry_interval_s=0.01)

            self.assertFalse(bus.is_ready())
            write_sentinel.assert_not_called()

    def test_port_is_free_probe_sets_reuseaddr(self) -> None:
        import socket as socket_module

        from lelamp.motor_bus import server as server_module

        fake_sock = mock.MagicMock()
        fake_sock.__enter__.return_value = fake_sock
        fake_sock.__exit__.return_value = False

        with mock.patch.object(server_module.socket, "socket", return_value=fake_sock) as mk:
            result = server_module._port_is_free("127.0.0.1", 8770)

        mk.assert_called_once_with(socket_module.AF_INET, socket_module.SOCK_STREAM)
        setsockopt_calls = [c for c in fake_sock.mock_calls if c[0] == "setsockopt"]
        self.assertIn(
            mock.call.setsockopt(socket_module.SOL_SOCKET, socket_module.SO_REUSEADDR, 1),
            fake_sock.mock_calls,
            "probe socket must set SO_REUSEADDR to match uvicorn; otherwise "
            "TIME_WAIT remnants are wrongly reported as busy for up to "
            "tcp_fin_timeout (~60s). See docs/acceptance/H0_pi_acceptance_20260418.md",
        )
        self.assertEqual(len(setsockopt_calls), 1, "exactly one setsockopt call expected")
        fake_sock.bind.assert_called_once_with(("127.0.0.1", 8770))
        self.assertTrue(result)

    def test_port_is_free_probe_returns_false_on_bind_error(self) -> None:
        from lelamp.motor_bus import server as server_module

        fake_sock = mock.MagicMock()
        fake_sock.__enter__.return_value = fake_sock
        fake_sock.__exit__.return_value = False
        fake_sock.bind.side_effect = OSError("EADDRINUSE")

        with mock.patch.object(server_module.socket, "socket", return_value=fake_sock):
            result = server_module._port_is_free("127.0.0.1", 8770)

        self.assertFalse(result)

    def test_start_default_retry_is_thirty_seconds(self) -> None:
        # Regression guard for H0.3: 12s was insufficient to cover a listener
        # whose owner PID was still alive ~1-2s after systemctl restart plus
        # an overlap with the kernel's TIME_WAIT bookkeeping. Default must
        # stay at 30s unless the retry budget is revisited deliberately.
        import inspect

        from lelamp.motor_bus import server as server_module

        sig = inspect.signature(server_module.MotorBusServer.start)
        self.assertEqual(
            sig.parameters["bind_retry_total_s"].default,
            30.0,
            "default bind_retry_total_s must be 30.0; see H0.3 in "
            "docs/acceptance/H0_pi_acceptance_20260418.md",
        )


if __name__ == "__main__":
    unittest.main()
