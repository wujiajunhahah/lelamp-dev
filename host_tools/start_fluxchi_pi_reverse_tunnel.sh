#!/usr/bin/env bash

set -euo pipefail

PI_HOST="${PI_HOST:-wujiajun@10.161.139.125}"
SSH_PORT="${SSH_PORT:-2222}"
REMOTE_PORT="${REMOTE_PORT:-18000}"
LOCAL_PORT="${LOCAL_PORT:-8000}"
SSH_FOREGROUND="${SSH_FOREGROUND:-0}"

ssh_args=(
  -F /dev/null
  -N
  -T
  -p "${SSH_PORT}" \
  -o BatchMode=yes \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=3 \
  -R "${REMOTE_PORT}:127.0.0.1:${LOCAL_PORT}" \
)

if [[ "${SSH_FOREGROUND}" != "1" ]]; then
  ssh_args=(-f "${ssh_args[@]}")
fi

exec ssh "${ssh_args[@]}" "${PI_HOST}"
