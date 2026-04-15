#!/usr/bin/env bash
set -euo pipefail

PI_USER="${LELAMP_PI_USER:-wujiajun}"
SSH_TIMEOUT="${LELAMP_PI_SSH_TIMEOUT:-4}"

DEFAULT_LOCAL_CANDIDATES="${PI_USER}@lelamp.local,${PI_USER}@raspberrypi.local,${PI_USER}@172.20.10.2"
LOCAL_CANDIDATES="${LELAMP_PI_LOCAL_CANDIDATES:-$DEFAULT_LOCAL_CANDIDATES}"
TAILSCALE_NAME="${LELAMP_PI_TAILSCALE_NAME:-}"
TAILSCALE_HOST="${LELAMP_PI_TAILSCALE_HOST:-}"
EXPLICIT_HOST="${1:-}"

normalize_target() {
  local target="${1:-}"
  if [[ -z "$target" ]]; then
    return 1
  fi
  if [[ "$target" == *"@"* ]]; then
    printf '%s\n' "$target"
    return 0
  fi
  printf '%s@%s\n' "$PI_USER" "$target"
}

probe_target() {
  local target="$1"
  ssh \
    -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new \
    -o ConnectTimeout="$SSH_TIMEOUT" \
    "$target" \
    "exit 0" >/dev/null 2>&1
}

iter_candidates() {
  local raw="$1"
  printf '%s\n' "$raw" | tr ',' '\n' | while IFS= read -r candidate; do
    candidate="${candidate#"${candidate%%[![:space:]]*}"}"
    candidate="${candidate%"${candidate##*[![:space:]]}"}"
    if [[ -n "$candidate" ]]; then
      normalize_target "$candidate"
    fi
  done
}

first_responsive_target() {
  local candidates="$1"
  while IFS= read -r candidate; do
    if probe_target "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done < <(iter_candidates "$candidates")
  return 1
}

if [[ -n "$EXPLICIT_HOST" ]]; then
  normalize_target "$EXPLICIT_HOST"
  exit 0
fi

if [[ -n "${LELAMP_PI_HOST:-}" ]]; then
  normalize_target "${LELAMP_PI_HOST}"
  exit 0
fi

if resolved="$(first_responsive_target "$LOCAL_CANDIDATES")"; then
  printf '%s\n' "$resolved"
  exit 0
fi

tailscale_candidates=""
if [[ -n "$TAILSCALE_HOST" ]]; then
  tailscale_candidates="$TAILSCALE_HOST"
fi
if [[ -n "$TAILSCALE_NAME" ]]; then
  if [[ -n "$tailscale_candidates" ]]; then
    tailscale_candidates+=","
  fi
  tailscale_candidates+="$TAILSCALE_NAME"
fi

if [[ -n "$tailscale_candidates" ]] && resolved="$(first_responsive_target "$tailscale_candidates")"; then
  printf '%s\n' "$resolved"
  exit 0
fi

echo "Unable to resolve a reachable LeLamp Pi host." >&2
echo "Tried local candidates: ${LOCAL_CANDIDATES}" >&2
if [[ -n "$tailscale_candidates" ]]; then
  echo "Tried Tailscale candidates: ${tailscale_candidates}" >&2
else
  echo "Set LELAMP_PI_TAILSCALE_NAME or LELAMP_PI_TAILSCALE_HOST to enable Tailscale fallback." >&2
fi
exit 1
