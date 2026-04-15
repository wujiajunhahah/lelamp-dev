#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_HOST_INPUT="${1:-}"
TAILSCALE_AUTH_KEY="${TAILSCALE_AUTH_KEY:-}"
TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME:-${LELAMP_PI_TAILSCALE_NAME:-lelamp-pi5}}"
TAILSCALE_ENABLE_SSH="${TAILSCALE_ENABLE_SSH:-1}"

single_quote() {
  printf "%s" "$1" | sed "s/'/'\"'\"'/g"
}

if ! command -v ssh >/dev/null 2>&1; then
  echo "ssh is required locally." >&2
  exit 1
fi

if [[ -n "$TARGET_HOST_INPUT" ]]; then
  TARGET_HOST="$(bash "${PROJECT_ROOT}/scripts/resolve_pi_host.sh" "$TARGET_HOST_INPUT")"
else
  TARGET_HOST="$(bash "${PROJECT_ROOT}/scripts/resolve_pi_host.sh")"
fi

SSH_FLAG=""
if [[ "$TAILSCALE_ENABLE_SSH" == "1" ]]; then
  SSH_FLAG="--ssh "
fi

QUOTED_HOSTNAME="$(single_quote "$TAILSCALE_HOSTNAME")"
QUOTED_AUTH_KEY="$(single_quote "$TAILSCALE_AUTH_KEY")"

echo "[tailscale] target=${TARGET_HOST}"
echo "[tailscale] hostname=${TAILSCALE_HOSTNAME}"
echo "[tailscale] auto_reconnect=enabled"

read -r -d '' REMOTE_BOOTSTRAP <<EOF || true
set -euo pipefail
if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
sudo systemctl enable --now tailscaled
if [[ -n '${QUOTED_AUTH_KEY}' ]]; then
  sudo tailscale up ${SSH_FLAG}--hostname '${QUOTED_HOSTNAME}' --auth-key '${QUOTED_AUTH_KEY}'
elif sudo tailscale ip -4 >/dev/null 2>&1; then
  echo "tailscale already connected"
else
  echo "tailscale installed and service enabled"
  echo "Run on the Pi once: sudo tailscale up ${SSH_FLAG}--hostname '${QUOTED_HOSTNAME}'" >&2
fi
EOF

ssh "${TARGET_HOST}" "${REMOTE_BOOTSTRAP}"

echo "[tailscale] done"
