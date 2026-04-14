import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient

from lelamp.dashboard.api import create_app
from lelamp.dashboard.runtime_bridge import DashboardActionResult
from lelamp.dashboard.state_store import DashboardStateStore


class FakeExecutor:
    def __init__(self, *, busy: bool = False) -> None:
        self.busy = busy
        self.active = None

    def is_busy(self) -> bool:
        return self.busy

    def current_action(self) -> str | None:
        return self.active

    def submit(self, action_id, callback, *, section, success_patch):
        if self.busy:
            return SimpleNamespace(
                ok=False,
                action_id=action_id,
                state="busy",
                message="Another action is already running.",
                error="busy",
            )
        self.active = action_id
        return SimpleNamespace(
            ok=True,
            action_id=action_id,
            state="running",
            message=f"{action_id} started.",
            error=None,
        )


class FakeBridge:
    settings = SimpleNamespace(home_recording="home_safe")

    def list_recordings(self) -> list[str]:
        return ["curious", "wake_up"]

    def startup(self) -> DashboardActionResult:
        return DashboardActionResult(True, "startup complete")

    def stop(self) -> DashboardActionResult:
        return DashboardActionResult(True, "stopped")

    def shutdown_pose(self) -> DashboardActionResult:
        return DashboardActionResult(True, "shutdown complete")

    def play(self, name: str) -> DashboardActionResult:
        return DashboardActionResult(True, f"played {name}")

    def set_light_solid(self, rgb) -> DashboardActionResult:
        return DashboardActionResult(True, f"rgb {rgb}")

    def clear_light(self) -> DashboardActionResult:
        return DashboardActionResult(True, "cleared")


class DashboardApiTests(unittest.TestCase):
    def test_get_state_returns_snapshot(self) -> None:
        settings = SimpleNamespace(
            dashboard_host="0.0.0.0",
            dashboard_port=8765,
            dashboard_poll_ms=400,
        )
        app = create_app(
            settings=settings,
            store=DashboardStateStore(),
            bridge=FakeBridge(),
            executor=FakeExecutor(),
            enable_background=False,
        )
        client = TestClient(app)

        response = client.get("/api/state")

        self.assertEqual(response.status_code, 200)
        self.assertIn("system", response.json())

    def test_post_startup_returns_running_receipt(self) -> None:
        settings = SimpleNamespace(
            dashboard_host="0.0.0.0",
            dashboard_port=8765,
            dashboard_poll_ms=400,
        )
        app = create_app(
            settings=settings,
            store=DashboardStateStore(),
            bridge=FakeBridge(),
            executor=FakeExecutor(),
            enable_background=False,
        )
        client = TestClient(app)

        response = client.post("/api/actions/startup")

        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["action_id"], "startup")

    def test_post_startup_returns_busy_when_executor_rejects(self) -> None:
        settings = SimpleNamespace(
            dashboard_host="0.0.0.0",
            dashboard_port=8765,
            dashboard_poll_ms=400,
        )
        app = create_app(
            settings=settings,
            store=DashboardStateStore(),
            bridge=FakeBridge(),
            executor=FakeExecutor(busy=True),
            enable_background=False,
        )
        client = TestClient(app)

        response = client.post("/api/actions/startup")

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()["ok"])
        self.assertEqual(response.json()["error"], "busy")


if __name__ == "__main__":
    unittest.main()
