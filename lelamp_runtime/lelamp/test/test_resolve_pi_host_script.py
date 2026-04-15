import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "resolve_pi_host.sh"


class ResolvePiHostScriptTests(unittest.TestCase):
    def test_explicit_host_bypasses_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            fake_bin = temp_root / "bin"
            fake_bin.mkdir()
            ssh_log = temp_root / "ssh.log"

            self._write_executable(
                fake_bin / "ssh",
                f"""#!/bin/sh
printf '%s\\n' "$*" >> "{ssh_log}"
exit 1
""",
            )

            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

            result = subprocess.run(
                ["bash", str(SCRIPT), "pi-control.local"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertEqual(result.stdout.strip(), "wujiajun@pi-control.local")
            self.assertFalse(ssh_log.exists(), "explicit host should not trigger ssh probes")

    def test_prefers_reachable_local_candidate_before_tailscale(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            fake_bin = temp_root / "bin"
            fake_bin.mkdir()
            ssh_log = temp_root / "ssh.log"

            self._write_executable(
                fake_bin / "ssh",
                f"""#!/bin/sh
printf '%s\\n' "$*" >> "{ssh_log}"
case "$*" in
  *"wujiajun@pi-local-good"*)
    exit 0
    ;;
  *)
    exit 1
    ;;
esac
""",
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}:{env.get('PATH', '')}",
                    "LELAMP_PI_LOCAL_CANDIDATES": "pi-local-bad,pi-local-good",
                    "LELAMP_PI_TAILSCALE_NAME": "lelamp-tailnet",
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
            self.assertEqual(result.stdout.strip(), "wujiajun@pi-local-good")
            ssh_invocations = ssh_log.read_text(encoding="utf-8")
            self.assertIn("wujiajun@pi-local-bad", ssh_invocations)
            self.assertIn("wujiajun@pi-local-good", ssh_invocations)
            self.assertNotIn("lelamp-tailnet", ssh_invocations)

    def test_falls_back_to_tailscale_when_local_candidates_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            fake_bin = temp_root / "bin"
            fake_bin.mkdir()
            ssh_log = temp_root / "ssh.log"

            self._write_executable(
                fake_bin / "ssh",
                f"""#!/bin/sh
printf '%s\\n' "$*" >> "{ssh_log}"
case "$*" in
  *"wujiajun@lelamp-tailnet"*)
    exit 0
    ;;
  *)
    exit 1
    ;;
esac
""",
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}:{env.get('PATH', '')}",
                    "LELAMP_PI_LOCAL_CANDIDATES": "pi-local-a,pi-local-b",
                    "LELAMP_PI_TAILSCALE_NAME": "lelamp-tailnet",
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
            self.assertEqual(result.stdout.strip(), "wujiajun@lelamp-tailnet")
            ssh_invocations = ssh_log.read_text(encoding="utf-8")
            self.assertIn("wujiajun@pi-local-a", ssh_invocations)
            self.assertIn("wujiajun@pi-local-b", ssh_invocations)
            self.assertIn("wujiajun@lelamp-tailnet", ssh_invocations)

    @staticmethod
    def _write_executable(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


if __name__ == "__main__":
    unittest.main()
