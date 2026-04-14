import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "sync_pi_runtime.sh"


class SyncPiRuntimeScriptTests(unittest.TestCase):
    def test_start_dashboard_restart_command_avoids_self_matching_pkill_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            fake_bin = temp_root / "bin"
            fake_bin.mkdir()
            ssh_log = temp_root / "ssh.log"
            rsync_log = temp_root / "rsync.log"

            self._write_executable(
                fake_bin / "ssh",
                f"""#!/bin/sh
printf '%s\\n' "$*" >> "{ssh_log}"
case "$*" in
  *"pkill -f 'lelamp.dashboard.api'"*)
    echo "unsafe pkill pattern matched remote shell" >&2
    exit 255
    ;;
  *)
    exit 0
    ;;
esac
""",
            )
            self._write_executable(
                fake_bin / "rsync",
                f"""#!/bin/sh
printf '%s\\n' "$*" >> "{rsync_log}"
exit 0
""",
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}:{env.get('PATH', '')}",
                    "INSTALL_DASHBOARD_DEPS": "0",
                    "VERIFY_DASHBOARD": "0",
                    "START_DASHBOARD": "1",
                    "SYNC_DELETE": "0",
                }
            )

            result = subprocess.run(
                ["bash", str(SCRIPT)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            ssh_invocations = ssh_log.read_text(encoding="utf-8")
            self.assertIn("mkdir -p", ssh_invocations)
            self.assertIn("pkill -f '^./\\.venv/bin/python -m lelamp\\.dashboard\\.api$'", ssh_invocations)
            self.assertIn("nohup ./.venv/bin/python -m lelamp.dashboard.api", ssh_invocations)
            self.assertTrue(rsync_log.read_text(encoding="utf-8").strip())

    @staticmethod
    def _write_executable(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


if __name__ == "__main__":
    unittest.main()
