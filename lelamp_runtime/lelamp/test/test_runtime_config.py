import os
import tempfile
import unittest
from pathlib import Path
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

    def test_runtime_settings_load_dotenv_from_working_directory(self) -> None:
        previous_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                Path(tmp_dir, ".env").write_text(
                    "LELAMP_STARTUP_RECORDING=wake_up\n"
                    "LELAMP_HOME_RECORDING=home_safe\n"
                    "LELAMP_IDLE_RECORDING=home_safe\n",
                    encoding="utf-8",
                )
                os.chdir(tmp_dir)
                with patch.dict(os.environ, {}, clear=True):
                    settings = load_runtime_settings()
        finally:
            os.chdir(previous_cwd)

        self.assertEqual(settings.startup_recording, "wake_up")
        self.assertEqual(settings.home_recording, "home_safe")
        self.assertEqual(settings.idle_recording, "home_safe")


if __name__ == "__main__":
    unittest.main()
