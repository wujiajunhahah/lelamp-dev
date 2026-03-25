#!/usr/bin/env bash

set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this script as your normal Raspberry Pi user, not root."
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUTO_ACCEPT_DEFAULTS="${AUTO_ACCEPT_DEFAULTS:-0}"
AUTO_REBOOT="${AUTO_REBOOT:-0}"
ALLOW_NON_PI5="${ALLOW_NON_PI5:-0}"

LAMP_ID="${LAMP_ID:-lelamp}"
LAMP_PORT="${LAMP_PORT:-/dev/ttyACM0}"
MODE_SCRIPT="${MODE_SCRIPT:-smooth_animation.py}"
RESPEAKER_VARIANT="${RESPEAKER_VARIANT:-auto}"

INSTALL_LELAMP_SERVICE="${INSTALL_LELAMP_SERVICE:-1}"
INSTALL_OPENCLAW="${INSTALL_OPENCLAW:-1}"
OPENCLAW_INSTALL_MODE="${OPENCLAW_INSTALL_MODE:-standard}"
INSTALL_TAILSCALE="${INSTALL_TAILSCALE:-0}"
RUN_OPENCLAW_ONBOARD="${RUN_OPENCLAW_ONBOARD:-0}"
RUN_DOWNLOAD_FILES_POSTBOOT="${RUN_DOWNLOAD_FILES_POSTBOOT:-1}"

OPENAI_API_KEY="${OPENAI_API_KEY:-}"
LIVEKIT_URL="${LIVEKIT_URL:-}"
LIVEKIT_API_KEY="${LIVEKIT_API_KEY:-}"
LIVEKIT_API_SECRET="${LIVEKIT_API_SECRET:-}"

PI_MODEL="$(tr -d '\0' </proc/device-tree/model 2>/dev/null || true)"
ARCH="$(uname -m)"
OS_CODENAME="$(. /etc/os-release && printf '%s' "${VERSION_CODENAME:-unknown}")"
ENV_FILE="${REPO_ROOT}/.env"
POST_BOOT_ENV_FILE="${REPO_ROOT}/.pi5_post_boot.env"
POST_BOOT_SERVICE_PATH="/etc/systemd/system/lelamp-post-bootstrap.service"

log() {
  printf '\n==> %s\n' "$*"
}

prompt_default() {
  local var_name="$1"
  local prompt_text="$2"
  local default_value="$3"
  local response

  if [[ -n "${!var_name:-}" ]]; then
    return
  fi

  if [[ "$AUTO_ACCEPT_DEFAULTS" == "1" || ! -t 0 ]]; then
    printf -v "$var_name" '%s' "$default_value"
    return
  fi

  read -r -p "${prompt_text} [${default_value}]: " response
  printf -v "$var_name" '%s' "${response:-$default_value}"
}

prompt_yes_no() {
  local var_name="$1"
  local prompt_text="$2"
  local default_value="$3"
  local response

  if [[ "${!var_name:-}" == "0" || "${!var_name:-}" == "1" ]]; then
    return
  fi

  if [[ "$AUTO_ACCEPT_DEFAULTS" == "1" || ! -t 0 ]]; then
    printf -v "$var_name" '%s' "$default_value"
    return
  fi

  local default_hint="y/N"
  if [[ "$default_value" == "1" ]]; then
    default_hint="Y/n"
  fi

  while true; do
    read -r -p "${prompt_text} [${default_hint}]: " response
    response="${response:-}"
    if [[ -z "$response" ]]; then
      printf -v "$var_name" '%s' "$default_value"
      return
    fi
    case "${response,,}" in
      y|yes) printf -v "$var_name" '1'; return ;;
      n|no) printf -v "$var_name" '0'; return ;;
    esac
  done
}

prompt_secret() {
  local var_name="$1"
  local prompt_text="$2"
  local response

  if [[ -n "${!var_name:-}" ]]; then
    return
  fi

  if [[ "$AUTO_ACCEPT_DEFAULTS" == "1" || ! -t 0 ]]; then
    return
  fi

  read -r -s -p "${prompt_text}: " response
  printf '\n'
  printf -v "$var_name" '%s' "$response"
}

upsert_env() {
  local key="$1"
  local value="$2"

  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

ensure_pi_profile() {
  if [[ "$PI_MODEL" != *"Raspberry Pi 5"* && "$ALLOW_NON_PI5" != "1" ]]; then
    echo "This installer is tuned for Raspberry Pi 5, but detected: ${PI_MODEL:-unknown}" >&2
    echo "If you really want to continue on another device, rerun with ALLOW_NON_PI5=1." >&2
    exit 1
  fi

  if [[ "$ARCH" != "aarch64" ]]; then
    echo "Expected 64-bit Raspberry Pi OS. Detected architecture: ${ARCH}" >&2
    echo "For the safest path, use Raspberry Pi OS Lite 64-bit on Pi 5." >&2
  fi
}

has_all_voice_secrets() {
  [[ -n "$OPENAI_API_KEY" && -n "$LIVEKIT_URL" && -n "$LIVEKIT_API_KEY" && -n "$LIVEKIT_API_SECRET" ]]
}

install_post_boot_service() {
  cat >"$POST_BOOT_ENV_FILE" <<EOF
MODE_SCRIPT=${MODE_SCRIPT}
RUN_DOWNLOAD_FILES_POSTBOOT=${RUN_DOWNLOAD_FILES_POSTBOOT}
CHECK_OPENCLAW=${INSTALL_OPENCLAW}
EOF

  sudo tee "$POST_BOOT_SERVICE_PATH" >/dev/null <<EOF
[Unit]
Description=LeLamp Pi 5 post-boot finalizer
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${REPO_ROOT}
ExecStart=/usr/bin/env bash -lc 'cd ${REPO_ROOT} && ${REPO_ROOT}/scripts/pi5_post_reboot_finalize.sh'
User=root

[Install]
WantedBy=multi-user.target
EOF

  sudo systemctl daemon-reload
  sudo systemctl enable lelamp-post-bootstrap.service
}

log "Detected Pi model: ${PI_MODEL:-unknown}"
log "Detected architecture: ${ARCH}"
log "Detected OS codename: ${OS_CODENAME}"

ensure_pi_profile

prompt_default LAMP_ID "Lamp ID" "$LAMP_ID"
prompt_default LAMP_PORT "Servo serial port" "$LAMP_PORT"
prompt_default MODE_SCRIPT "Runtime mode script (smooth_animation.py or main.py)" "$MODE_SCRIPT"
prompt_default RESPEAKER_VARIANT "ReSpeaker variant (auto, v2, v1, skip)" "$RESPEAKER_VARIANT"

prompt_yes_no INSTALL_LELAMP_SERVICE "Install and enable LeLamp boot service" "$INSTALL_LELAMP_SERVICE"
prompt_yes_no INSTALL_OPENCLAW "Install OpenClaw on this Pi" "$INSTALL_OPENCLAW"

if [[ "$INSTALL_OPENCLAW" == "1" ]]; then
  prompt_default OPENCLAW_INSTALL_MODE "OpenClaw install mode (standard, local, git)" "$OPENCLAW_INSTALL_MODE"
  prompt_yes_no INSTALL_TAILSCALE "Install Tailscale for private remote dashboard access" "$INSTALL_TAILSCALE"
  prompt_yes_no RUN_OPENCLAW_ONBOARD "Run OpenClaw onboarding now" "$RUN_OPENCLAW_ONBOARD"
fi

prompt_yes_no RUN_DOWNLOAD_FILES_POSTBOOT "Run LiveKit/OpenAI download step automatically after reboot" "$RUN_DOWNLOAD_FILES_POSTBOOT"
prompt_yes_no AUTO_REBOOT "Reboot automatically at the end of setup" "$AUTO_REBOOT"

prompt_secret OPENAI_API_KEY "OpenAI API key (leave blank to fill later)"
prompt_secret LIVEKIT_URL "LiveKit URL (leave blank to fill later)"
prompt_secret LIVEKIT_API_KEY "LiveKit API key (leave blank to fill later)"
prompt_secret LIVEKIT_API_SECRET "LiveKit API secret (leave blank to fill later)"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "${REPO_ROOT}/.env.example" "$ENV_FILE"
fi

upsert_env "LELAMP_ID" "$LAMP_ID"
upsert_env "LELAMP_PORT" "$LAMP_PORT"
upsert_env "LELAMP_AUDIO_USER" "$USER"

if [[ -n "$OPENAI_API_KEY" ]]; then upsert_env "OPENAI_API_KEY" "$OPENAI_API_KEY"; fi
if [[ -n "$LIVEKIT_URL" ]]; then upsert_env "LIVEKIT_URL" "$LIVEKIT_URL"; fi
if [[ -n "$LIVEKIT_API_KEY" ]]; then upsert_env "LIVEKIT_API_KEY" "$LIVEKIT_API_KEY"; fi
if [[ -n "$LIVEKIT_API_SECRET" ]]; then upsert_env "LIVEKIT_API_SECRET" "$LIVEKIT_API_SECRET"; fi

resolved_install_service="$INSTALL_LELAMP_SERVICE"
if [[ "$INSTALL_LELAMP_SERVICE" == "1" ]] && ! has_all_voice_secrets; then
  log "Voice service secrets are incomplete, so the LeLamp boot service will not be enabled yet."
  resolved_install_service="0"
fi

log "Running LeLamp Pi setup"
INSTALL_SERVICE="$resolved_install_service" \
MODE_SCRIPT="$MODE_SCRIPT" \
LAMP_ID="$LAMP_ID" \
LAMP_PORT="$LAMP_PORT" \
RESPEAKER_VARIANT="$RESPEAKER_VARIANT" \
  "${REPO_ROOT}/scripts/pi_setup_max.sh"

if [[ "$INSTALL_OPENCLAW" == "1" ]]; then
  log "Running OpenClaw setup"
  INSTALL_TAILSCALE="$INSTALL_TAILSCALE" \
  RUN_ONBOARD="$RUN_OPENCLAW_ONBOARD" \
  OPENCLAW_INSTALL_MODE="$OPENCLAW_INSTALL_MODE" \
    "${REPO_ROOT}/scripts/openclaw_pi5_setup.sh"

  log "Installing LeLamp OpenClaw skill"
  "${REPO_ROOT}/scripts/install_openclaw_skill.sh"
fi

log "Installing post-reboot finalizer"
install_post_boot_service

cat <<EOF

Setup staged successfully.

Repo root: ${REPO_ROOT}
Lamp ID: ${LAMP_ID}
Servo port: ${LAMP_PORT}
Mode script: ${MODE_SCRIPT}
ReSpeaker path: ${RESPEAKER_VARIANT}
OpenClaw installed: ${INSTALL_OPENCLAW}
LeLamp boot service enabled now: ${resolved_install_service}

Next reboot will run:
- post-boot audio/device report
- optional download-files step
- optional OpenClaw status checks

After reboot, inspect:
- ${REPO_ROOT}/POST_BOOT_REPORT.md
- ${REPO_ROOT}/.env
EOF

if [[ "$AUTO_REBOOT" == "1" ]]; then
  log "Rebooting now"
  sudo reboot
else
  log "Reboot required. Rerun nothing; just reboot when ready."
fi
