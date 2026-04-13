import unittest

from lelamp.dashboard.state_store import DashboardStateStore


class DashboardStateStoreTests(unittest.TestCase):
    def test_snapshot_starts_with_unknown_sections(self) -> None:
        store = DashboardStateStore()
        snapshot = store.snapshot()

        self.assertEqual(snapshot["system"]["status"], "unknown")
        self.assertEqual(snapshot["motion"]["status"], "unknown")
        self.assertEqual(snapshot["light"]["status"], "unknown")
        self.assertEqual(snapshot["audio"]["status"], "unknown")
        self.assertEqual(snapshot["errors"], [])

    def test_patch_merges_nested_state_and_updates_timestamp(self) -> None:
        store = DashboardStateStore()
        first_update = store.snapshot()["system"]["last_update_ms"]

        snapshot = store.patch("motion", {"status": "idle", "current_recording": "home_safe"})

        self.assertEqual(snapshot["motion"]["status"], "idle")
        self.assertEqual(snapshot["motion"]["current_recording"], "home_safe")
        self.assertGreaterEqual(snapshot["system"]["last_update_ms"], first_update)

    def test_record_error_deduplicates_by_code_and_source(self) -> None:
        store = DashboardStateStore()

        store.record_error("motor.read_failed", "read timeout", "motors", "warning")
        snapshot = store.record_error("motor.read_failed", "read timeout", "motors", "warning")

        self.assertEqual(len(snapshot["errors"]), 1)
        self.assertTrue(snapshot["errors"][0]["active"])


if __name__ == "__main__":
    unittest.main()
