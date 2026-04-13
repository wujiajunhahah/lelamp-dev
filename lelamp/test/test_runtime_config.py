import os
import unittest
from unittest.mock import patch

from lelamp.runtime_config import load_runtime_settings


class RuntimeConfigTests(unittest.TestCase):
    def test_rgb_enabled_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = load_runtime_settings()

        self.assertTrue(settings.enable_rgb)

    def test_rgb_can_be_disabled_by_env(self) -> None:
        with patch.dict(os.environ, {"LELAMP_ENABLE_RGB": "false"}, clear=True):
            settings = load_runtime_settings()

        self.assertFalse(settings.enable_rgb)

    def test_home_pose_relative_flags_can_be_loaded(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LELAMP_IDLE_RECORDING": "home_safe",
                "LELAMP_HOME_RECORDING": "home_safe",
                "LELAMP_USE_HOME_POSE_RELATIVE": "true",
            },
            clear=True,
        ):
            settings = load_runtime_settings()

        self.assertEqual(settings.home_recording, "home_safe")
        self.assertTrue(settings.use_home_pose_relative)


if __name__ == "__main__":
    unittest.main()
