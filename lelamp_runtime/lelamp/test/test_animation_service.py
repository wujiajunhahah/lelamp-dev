import sys
import types
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class AnimationServiceCompatibilityTests(unittest.TestCase):
    def test_constructor_accepts_dashboard_runtime_kwargs(self) -> None:
        fake_follower_module = types.ModuleType("lelamp.follower")

        class FakeFollowerConfig:
            def __init__(self, *, port: str, id: str, disable_torque_on_disconnect: bool = True) -> None:
                self.port = port
                self.id = id
                self.disable_torque_on_disconnect = disable_torque_on_disconnect

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
        self.assertFalse(service.robot_config.disable_torque_on_disconnect)
        self.assertTrue(service.wait_until_playback_complete(timeout=0.01))

    def test_load_recording_reanchors_non_home_recordings_relative_to_home_pose(self) -> None:
        fake_follower_module = types.ModuleType("lelamp.follower")

        class FakeFollowerConfig:
            def __init__(self, *, port: str, id: str, disable_torque_on_disconnect: bool = True) -> None:
                self.port = port
                self.id = id
                self.disable_torque_on_disconnect = disable_torque_on_disconnect

        class FakeFollower:
            pass

        fake_follower_module.LeLampFollowerConfig = FakeFollowerConfig
        fake_follower_module.LeLampFollower = FakeFollower

        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(
            sys.modules,
            {"lelamp.follower": fake_follower_module},
            clear=False,
        ):
            recordings_dir = Path(tmp_dir)
            recordings_dir.joinpath("home_safe.csv").write_text(
                "\n".join(
                    [
                        "timestamp,base_yaw.pos,base_pitch.pos,elbow_pitch.pos,wrist_roll.pos,wrist_pitch.pos",
                        "0.000000,3.071017,30.995671,32.141337,96.923077,70.990468",
                        "0.033333,3.071017,30.995671,32.141337,96.923077,70.990468",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            recordings_dir.joinpath("wake_up.csv").write_text(
                "\n".join(
                    [
                        "timestamp,base_yaw.pos,base_pitch.pos,elbow_pitch.pos,wrist_roll.pos,wrist_pitch.pos",
                        "0.000000,11.856171,-51.283096,76.995708,1.454898,69.621273",
                        "0.033333,16.856171,-46.283096,81.995708,22.599418,74.621273",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            sys.modules.pop("lelamp.service.motors.animation_service", None)
            from lelamp.service.motors.animation_service import AnimationService

            service = AnimationService(
                port="/dev/ttyACM0",
                lamp_id="lelamp",
                fps=30,
                duration=3.0,
                idle_recording="home_safe",
                home_recording="home_safe",
                use_home_pose_relative=True,
            )
            service.recordings_dir = str(recordings_dir)

            wake_up_actions = service._load_recording("wake_up")
            home_actions = service._load_recording("home_safe")

        self.assertEqual(home_actions[0]["wrist_roll.pos"], 96.923077)
        self.assertEqual(wake_up_actions[0]["wrist_roll.pos"], 96.923077)
        self.assertAlmostEqual(wake_up_actions[1]["wrist_roll.pos"], 118.067597)
        self.assertAlmostEqual(wake_up_actions[0]["base_pitch.pos"], 30.995671)
        self.assertAlmostEqual(wake_up_actions[1]["base_pitch.pos"], 35.995671)


if __name__ == "__main__":
    unittest.main()
