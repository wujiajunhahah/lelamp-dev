import os
import unittest
from unittest.mock import patch

from lelamp.runtime_config import load_runtime_settings


class DashboardRuntimeConfigTests(unittest.TestCase):
    def test_load_runtime_settings_includes_dashboard_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = load_runtime_settings()

        self.assertEqual(settings.dashboard_host, "0.0.0.0")
        self.assertEqual(settings.dashboard_port, 8765)
        self.assertEqual(settings.dashboard_poll_ms, 400)


if __name__ == "__main__":
    unittest.main()
