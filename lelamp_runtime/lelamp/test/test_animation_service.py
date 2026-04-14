import sys
import types
import unittest
from unittest.mock import patch


class AnimationServiceCompatibilityTests(unittest.TestCase):
    def test_constructor_accepts_dashboard_runtime_kwargs(self) -> None:
        fake_follower_module = types.ModuleType("lelamp.follower")

        class FakeFollowerConfig:
            def __init__(self, *, port: str, id: str) -> None:
                self.port = port
                self.id = id

        class FakeFollower:
            pass

        fake_follower_module.LeLampFollowerConfig = FakeFollowerConfig
        fake_follower_module.LeLampFollower = FakeFollower

        with patch.dict(sys.modules, {"lelamp.follower": fake_follower_module}, clear=False):
            sys.modules.pop("lelamp.service.motors.animation_service", None)
            from lelamp.service.motors.animation_service import AnimationService

            service = AnimationService(
                port="/dev/ttyACM0",
                lamp_id="lelamp",
                fps=30,
                duration=3.0,
                idle_recording="idle",
                home_recording="home_safe",
                use_home_pose_relative=True,
            )

        self.assertEqual(service.idle_recording, "idle")
        self.assertEqual(service.home_recording, "home_safe")
        self.assertTrue(service.use_home_pose_relative)
        self.assertTrue(service.wait_until_playback_complete(timeout=0.01))


if __name__ == "__main__":
    unittest.main()
