import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class BootServiceTests(unittest.TestCase):
    def test_service_example_uses_local_console_mode(self) -> None:
        unit = (ROOT / "scripts" / "lelamp.service.example").read_text(encoding="utf-8")

        self.assertIn("smooth_animation.py console", unit)
        self.assertNotIn("smooth_animation.py start", unit)
        self.assertIn("User=pi", unit)
        self.assertNotIn("User=root", unit)

    def test_pi_setup_max_installs_console_mode_service(self) -> None:
        script = (ROOT / "scripts" / "pi_setup_max.sh").read_text(encoding="utf-8")

        self.assertIn("${UV_BIN} run ${MODE_SCRIPT} console", script)
        self.assertNotIn("${UV_BIN} run ${MODE_SCRIPT} start", script)
        self.assertIn("User=${SERVICE_USER}", script)
        self.assertIn("KERNEL==\"leds0\", MODE=\"0660\", GROUP=\"gpio\"", script)


if __name__ == "__main__":
    unittest.main()
