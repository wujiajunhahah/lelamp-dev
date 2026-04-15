#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI_USER="${LELAMP_PI_USER:-wujiajun}"
TARGET_HOST_INPUT="${1:-}"
REMOTE_BASE="${2:-/home/${PI_USER}/lelamp-dev}"
REMOTE_RUNTIME="${REMOTE_BASE%/}/lelamp_runtime"

INSTALL_DASHBOARD_DEPS="${INSTALL_DASHBOARD_DEPS:-1}"
VERIFY_DASHBOARD="${VERIFY_DASHBOARD:-1}"
START_DASHBOARD="${START_DASHBOARD:-0}"
SYNC_DELETE="${SYNC_DELETE:-0}"

if [[ -n "$TARGET_HOST_INPUT" ]]; then
  TARGET_HOST="$(bash "${PROJECT_ROOT}/scripts/resolve_pi_host.sh" "$TARGET_HOST_INPUT")"
else
  TARGET_HOST="$(bash "${PROJECT_ROOT}/scripts/resolve_pi_host.sh")"
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required locally." >&2
  exit 1
fi

if ! command -v ssh >/dev/null 2>&1; then
  echo "ssh is required locally." >&2
  exit 1
fi

echo "[sync] target=${TARGET_HOST}"
echo "[sync] remote_runtime=${REMOTE_RUNTIME}"

ssh "${TARGET_HOST}" "mkdir -p '${REMOTE_RUNTIME}'"

RSYNC_ARGS=(
  -az
  --exclude ".git/" \
  --exclude ".venv/" \
  --exclude ".env" \
  --exclude "__pycache__/" \
  --exclude ".pytest_cache/" \
  --exclude ".mypy_cache/" \
  --exclude ".ruff_cache/" \
  --exclude ".DS_Store" \
  --exclude "*.pyc"
)

if [[ "${SYNC_DELETE}" == "1" ]]; then
  RSYNC_ARGS+=(--delete)
fi

rsync "${RSYNC_ARGS[@]}" "${PROJECT_ROOT}/" "${TARGET_HOST}:${REMOTE_RUNTIME}/"

if [[ "${INSTALL_DASHBOARD_DEPS}" == "1" ]]; then
  echo "[sync] installing dashboard runtime deps on Pi"
  ssh "${TARGET_HOST}" \
    "cd '${REMOTE_RUNTIME}' && ./.venv/bin/python -m pip install 'fastapi>=0.115,<1.0' 'uvicorn>=0.34,<1.0'"
fi

if [[ "${VERIFY_DASHBOARD}" == "1" ]]; then
  echo "[sync] running dashboard smoke tests on Pi"
  ssh "${TARGET_HOST}" \
    "cd '${REMOTE_RUNTIME}' && ./.venv/bin/python -m unittest lelamp.test.test_dashboard_api lelamp.test.test_dashboard_web -v"
fi

if [[ "${START_DASHBOARD}" == "1" ]]; then
  echo "[sync] restarting dashboard on Pi"
  ssh "${TARGET_HOST}" \
    "cd '${REMOTE_RUNTIME}' && { pkill -f '^./\\.venv/bin/python -m lelamp\\.dashboard\\.api$' >/dev/null 2>&1 || true; nohup ./.venv/bin/python -m lelamp.dashboard.api >/tmp/lelamp-dashboard.log 2>&1 < /dev/null & }"
  echo "[sync] dashboard log: /tmp/lelamp-dashboard.log"
fi

echo "[sync] done"
