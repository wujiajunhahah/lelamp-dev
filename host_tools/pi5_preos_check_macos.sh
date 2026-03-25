#!/usr/bin/env bash

set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This pre-OS helper is currently written for macOS." >&2
  exit 1
fi

echo
echo "== LeLamp Pi 5 pre-OS check for macOS =="
echo

if [[ -d "/Applications/Raspberry Pi Imager.app" ]]; then
  echo "[OK] Raspberry Pi Imager.app found in /Applications"
elif command -v rpi-imager >/dev/null 2>&1; then
  echo "[OK] rpi-imager command found: $(command -v rpi-imager)"
else
  echo "[WARN] Raspberry Pi Imager not found."
  echo "       Install it from the official Raspberry Pi software page before flashing the SD card."
fi

echo
echo "== External removable disks =="
diskutil list external physical || true

echo
echo "== Recommended Raspberry Pi Imager settings =="
cat <<'EOF'
Device:
  Raspberry Pi 5

OS:
  Raspberry Pi OS Lite 64-bit

OS customisation:
  - Set hostname
  - Create username/password
  - Configure Wi-Fi
  - Enable SSH
  - Set locale/timezone

After first boot:
  ssh <user>@<hostname>.local
  cd ~/lelamp_runtime
  ./scripts/pi5_all_in_one.sh
EOF

echo
echo "== Official alternatives =="
echo "1. Raspberry Pi Imager on your Mac"
echo "2. Raspberry Pi 5 Network Install with monitor + keyboard + Ethernet"
