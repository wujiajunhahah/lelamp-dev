import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FluxChiRemoteSetupTests(unittest.TestCase):
    def test_sidecar_installer_defers_listener_runtime_env_expansion(self) -> None:
        script = (
            ROOT / "lelamp_runtime" / "scripts" / "install_fluxchi_sidecars.sh"
        ).read_text(encoding="utf-8")

        self.assertIn('EnvironmentFile=-${LISTENER_ENV_FILE}', script)
        self.assertIn('ExecStart=/usr/bin/env bash -lc', script)
        self.assertIn(r'"\${FLUXCHI_WS}"', script)
        self.assertIn(r'"\${FLUXCHI_PROFILE_PATH}"', script)
        self.assertIn(r'"\${LELAMP_DASHBOARD}"', script)
        self.assertIn(r'"\${FLUXCHI_LOG_LEVEL}"', script)
        self.assertIn(r'\${FLUXCHI_DISABLE_VOICE_GATE:+--no-voice-gate}', script)

    def test_mac_reverse_tunnel_defaults_to_hardened_port(self) -> None:
        helper = (ROOT / "host_tools" / "start_fluxchi_pi_reverse_tunnel.sh").read_text(
            encoding="utf-8"
        )
        plist = (
            ROOT / "host_tools" / "com.wujiajun.fluxchi-pi-bridge.plist"
        ).read_text(encoding="utf-8")

        self.assertIn('SSH_PORT="${SSH_PORT:-2222}"', helper)
        self.assertIn("<string>2222</string>", plist)


if __name__ == "__main__":
    unittest.main()
