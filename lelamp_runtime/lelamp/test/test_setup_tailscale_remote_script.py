import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "setup_tailscale_remote.sh"


class SetupTailscaleRemoteScriptTests(unittest.TestCase):
    def test_installs_and_bootstraps_tailscale_with_auth_key(self) -> None:
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
  *"wujiajun@pi.test"*)
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
                    "LELAMP_PI_LOCAL_CANDIDATES": "pi.test",
                    "TAILSCALE_AUTH_KEY": "tskey-example",
                    "TAILSCALE_HOSTNAME": "lelamp-pi5",
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
            self.assertIn("wujiajun@pi.test", ssh_invocations)
            self.assertIn("tailscale.com/install.sh", ssh_invocations)
            self.assertIn("systemctl enable --now tailscaled", ssh_invocations)
            self.assertIn("tailscale up --ssh", ssh_invocations)
            self.assertIn("--hostname 'lelamp-pi5'", ssh_invocations)
            self.assertIn("--auth-key 'tskey-example'", ssh_invocations)

    @staticmethod
    def _write_executable(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


if __name__ == "__main__":
    unittest.main()
