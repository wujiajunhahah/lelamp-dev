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
        self._done = threading.Event()
        self._done.set()

    def get_available_recordings(self) -> list[str]:
        return list(self.recordings)

    def dispatch(self, event_type: str, payload: Any) -> None:
        self.dispatched.append((event_type, payload))

    def begin_playback(self) -> None:
        self._done.clear()

    def end_playback(self) -> None:
        self._done.set()

    def wait_until_playback_complete(self, timeout: float | None = None) -> bool:
        return self._done.wait(timeout=timeout)


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


if __name__ == "__main__":
    unittest.main()
