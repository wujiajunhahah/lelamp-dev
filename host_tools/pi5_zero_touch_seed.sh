#!/usr/bin/env bash

set -euo pipefail

BOOTFS_PATH="${BOOTFS_PATH:-}"
BOOTSTRAP_HOSTNAME="${BOOTSTRAP_HOSTNAME:-lelamp-pi5}"
BOOTSTRAP_USER="${BOOTSTRAP_USER:-pi}"
BOOTSTRAP_PASSWORD="${BOOTSTRAP_PASSWORD:-}"
BOOTSTRAP_WIFI_SSID="${BOOTSTRAP_WIFI_SSID:-}"
BOOTSTRAP_WIFI_PASSWORD="${BOOTSTRAP_WIFI_PASSWORD:-}"
BOOTSTRAP_WIFI_COUNTRY="${BOOTSTRAP_WIFI_COUNTRY:-CN}"
BOOTSTRAP_WIFI_UUID="${BOOTSTRAP_WIFI_UUID:-}"
BOOTSTRAP_SSH_PUBLIC_KEY="${BOOTSTRAP_SSH_PUBLIC_KEY:-}"
BOOTSTRAP_REPO_URL="${BOOTSTRAP_REPO_URL:-https://github.com/wujiajunhahah/lelamp-dev.git}"
BOOTSTRAP_REPO_BRANCH="${BOOTSTRAP_REPO_BRANCH:-main}"
BOOTSTRAP_REPO_DIR="${BOOTSTRAP_REPO_DIR:-lelamp-dev}"

AUTO_ACCEPT_DEFAULTS="${AUTO_ACCEPT_DEFAULTS:-1}"
AUTO_REBOOT="${AUTO_REBOOT:-1}"
LAMP_ID="${LAMP_ID:-lelamp}"
LAMP_PORT="${LAMP_PORT:-auto}"
MODE_SCRIPT="${MODE_SCRIPT:-smooth_animation.py}"
MODEL_PROVIDER="${MODEL_PROVIDER:-glm}"
MODEL_API_KEY="${MODEL_API_KEY:-${ZAI_API_KEY:-${OPENAI_API_KEY:-}}}"
MODEL_BASE_URL="${MODEL_BASE_URL:-https://open.bigmodel.cn/api/paas/v4}"
MODEL_NAME="${MODEL_NAME:-glm-realtime}"
MODEL_VOICE="${MODEL_VOICE:-tongtong}"
RESPEAKER_VARIANT="${RESPEAKER_VARIANT:-auto}"
INSTALL_LELAMP_SERVICE="${INSTALL_LELAMP_SERVICE:-1}"
INSTALL_OPENCLAW="${INSTALL_OPENCLAW:-1}"
OPENCLAW_INSTALL_MODE="${OPENCLAW_INSTALL_MODE:-standard}"
INSTALL_TAILSCALE="${INSTALL_TAILSCALE:-0}"
RUN_OPENCLAW_ONBOARD="${RUN_OPENCLAW_ONBOARD:-0}"
RUN_DOWNLOAD_FILES_POSTBOOT="${RUN_DOWNLOAD_FILES_POSTBOOT:-1}"

LIVEKIT_URL="${LIVEKIT_URL:-}"
LIVEKIT_API_KEY="${LIVEKIT_API_KEY:-}"
LIVEKIT_API_SECRET="${LIVEKIT_API_SECRET:-}"

FORCE_WRITE="${FORCE_WRITE:-0}"

usage() {
  cat <<'EOF'
Usage:
  ./host_tools/pi5_zero_touch_seed.sh --bootfs /Volumes/bootfs --password '<login-password>' [options]

Required:
  --bootfs PATH               Mounted Raspberry Pi boot partition
  --password VALUE            Password for the bootstrap user on first boot

Optional:
  --hostname NAME             Pi hostname written for first boot
  --username NAME             Login user created on first boot
  --wifi-ssid SSID            Wi-Fi SSID to preconfigure through NetworkManager
  --wifi-password VALUE       Wi-Fi password
  --wifi-country CODE         Wi-Fi country code, default CN
  --ssh-public-key PATH       Public key copied to authorized_keys on first boot
  --repo-url URL              Repo cloned by first boot bootstrap service
  --repo-branch NAME          Repo branch, default main
  --repo-dir NAME             Repo checkout directory in the user home
  --force                     Overwrite existing firstrun/bootstrap files

All other installer knobs can be passed as environment variables:
  AUTO_ACCEPT_DEFAULTS AUTO_REBOOT LAMP_ID LAMP_PORT MODE_SCRIPT
  MODEL_PROVIDER MODEL_API_KEY MODEL_BASE_URL MODEL_NAME MODEL_VOICE
  RESPEAKER_VARIANT INSTALL_LELAMP_SERVICE INSTALL_OPENCLAW
  OPENCLAW_INSTALL_MODE INSTALL_TAILSCALE RUN_OPENCLAW_ONBOARD
  RUN_DOWNLOAD_FILES_POSTBOOT LIVEKIT_URL
  LIVEKIT_API_KEY LIVEKIT_API_SECRET
EOF
}

log() {
  printf '\n==> %s\n' "$*"
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || die "Required command not found: ${cmd}"
}

shell_escape() {
  printf '%q' "$1"
}

emit_env_kv() {
  local key="$1"
  local value="$2"
  printf '%s=%s\n' "$key" "$(shell_escape "$value")"
}

list_external_disks_hint() {
  if [[ "$(uname -s)" == "Darwin" ]]; then
    printf '\nExternal disks on this Mac:\n'
    diskutil list external physical || true
  elif command -v lsblk >/dev/null 2>&1; then
    printf '\nBlock devices on this host:\n'
    lsblk -o NAME,SIZE,TYPE,MOUNTPOINT || true
  fi
}

resolve_bootfs_file() {
  local relative_path="$1"

  if [[ -f "${BOOTFS_PATH}/${relative_path}" ]]; then
    printf '%s\n' "${BOOTFS_PATH}/${relative_path}"
    return 0
  fi

  if [[ -f "${BOOTFS_PATH}/firmware/${relative_path}" ]]; then
    printf '%s\n' "${BOOTFS_PATH}/firmware/${relative_path}"
    return 0
  fi

  return 1
}

generate_password_hash() {
  local password="$1"

  if command -v openssl >/dev/null 2>&1 && openssl passwd -6 "$password" >/dev/null 2>&1; then
    openssl passwd -6 "$password"
    return 0
  fi

  python3 -c 'import crypt, sys; print(crypt.crypt(sys.argv[1], crypt.mksalt(crypt.METHOD_SHA512)))' "$password"
}

patch_cmdline() {
  local cmdline_path="$1"
  local firstrun_boot_path="/boot/firstrun.sh"
  local existing

  if [[ "$cmdline_path" == */firmware/cmdline.txt ]]; then
    firstrun_boot_path="/boot/firmware/firstrun.sh"
  fi

  local token="systemd.run=${firstrun_boot_path} systemd.run_success_action=reboot systemd.unit=kernel-command-line.target"

  existing="$(<"$cmdline_path")"
  if [[ "$existing" == *"systemd.run=/boot/firstrun.sh"* || "$existing" == *"systemd.run=/boot/firmware/firstrun.sh"* ]]; then
    log "cmdline.txt already contains firstrun hook"
    return 0
  fi

  printf '%s %s\n' "$existing" "$token" >"$cmdline_path"
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --bootfs)
      BOOTFS_PATH="$2"
      shift 2
      ;;
    --hostname)
      BOOTSTRAP_HOSTNAME="$2"
      shift 2
      ;;
    --username)
      BOOTSTRAP_USER="$2"
      shift 2
      ;;
    --password)
      BOOTSTRAP_PASSWORD="$2"
      shift 2
      ;;
    --wifi-ssid)
      BOOTSTRAP_WIFI_SSID="$2"
      shift 2
      ;;
    --wifi-password)
      BOOTSTRAP_WIFI_PASSWORD="$2"
      shift 2
      ;;
    --wifi-country)
      BOOTSTRAP_WIFI_COUNTRY="$2"
      shift 2
      ;;
    --ssh-public-key)
      BOOTSTRAP_SSH_PUBLIC_KEY="$2"
      shift 2
      ;;
    --repo-url)
      BOOTSTRAP_REPO_URL="$2"
      shift 2
      ;;
    --repo-branch)
      BOOTSTRAP_REPO_BRANCH="$2"
      shift 2
      ;;
    --repo-dir)
      BOOTSTRAP_REPO_DIR="$2"
      shift 2
      ;;
    --force)
      FORCE_WRITE="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

need_cmd python3
need_cmd sed

if [[ -z "$BOOTFS_PATH" ]]; then
  list_external_disks_hint
  die "Pass the mounted boot partition with --bootfs"
fi

if [[ ! -d "$BOOTFS_PATH" ]]; then
  die "Boot partition path does not exist: ${BOOTFS_PATH}"
fi

CMDLINE_PATH="$(resolve_bootfs_file cmdline.txt)" || {
  list_external_disks_hint
  die "Could not find cmdline.txt in ${BOOTFS_PATH}"
}
CONFIG_PATH="$(resolve_bootfs_file config.txt)" || die "Could not find config.txt in ${BOOTFS_PATH}"
USERCONF_PATH="$(dirname "$CMDLINE_PATH")/userconf.txt"
FIRSTRUN_PATH="$(dirname "$CMDLINE_PATH")/firstrun.sh"
BOOTSTRAP_ENV_PATH="$(dirname "$CMDLINE_PATH")/lelamp-bootstrap.env"
AUTHORIZED_KEYS_STAGING="$(dirname "$CMDLINE_PATH")/lelamp-authorized_keys"

if [[ -z "$BOOTSTRAP_PASSWORD" ]]; then
  die "A login password is required. Pass it with --password"
fi

if [[ -n "$BOOTSTRAP_WIFI_SSID" && -z "$BOOTSTRAP_WIFI_PASSWORD" ]]; then
  die "You passed --wifi-ssid without --wifi-password"
fi

if [[ -n "$BOOTSTRAP_SSH_PUBLIC_KEY" && ! -f "$BOOTSTRAP_SSH_PUBLIC_KEY" ]]; then
  die "SSH public key file not found: ${BOOTSTRAP_SSH_PUBLIC_KEY}"
fi

if [[ -f "$FIRSTRUN_PATH" && "$FORCE_WRITE" != "1" ]]; then
  die "firstrun.sh already exists in bootfs. Re-run with --force to overwrite"
fi

if [[ -f "$BOOTSTRAP_ENV_PATH" && "$FORCE_WRITE" != "1" ]]; then
  die "lelamp-bootstrap.env already exists in bootfs. Re-run with --force to overwrite"
fi

if [[ -z "$BOOTSTRAP_WIFI_UUID" ]]; then
  BOOTSTRAP_WIFI_UUID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
fi

PASSWORD_HASH="$(generate_password_hash "$BOOTSTRAP_PASSWORD")"

log "Writing userconf.txt"
printf '%s:%s\n' "$BOOTSTRAP_USER" "$PASSWORD_HASH" >"$USERCONF_PATH"

log "Enabling SSH on first boot"
touch "$(dirname "$CMDLINE_PATH")/ssh"

if [[ -n "$BOOTSTRAP_SSH_PUBLIC_KEY" ]]; then
  log "Staging authorized_keys payload"
  cp "$BOOTSTRAP_SSH_PUBLIC_KEY" "$AUTHORIZED_KEYS_STAGING"
fi

log "Writing bootstrap environment"
{
  emit_env_kv BOOTSTRAP_HOSTNAME "$BOOTSTRAP_HOSTNAME"
  emit_env_kv BOOTSTRAP_USER "$BOOTSTRAP_USER"
  emit_env_kv BOOTSTRAP_WIFI_SSID "$BOOTSTRAP_WIFI_SSID"
  emit_env_kv BOOTSTRAP_WIFI_PASSWORD "$BOOTSTRAP_WIFI_PASSWORD"
  emit_env_kv BOOTSTRAP_WIFI_COUNTRY "$BOOTSTRAP_WIFI_COUNTRY"
  emit_env_kv BOOTSTRAP_WIFI_UUID "$BOOTSTRAP_WIFI_UUID"
  emit_env_kv BOOTSTRAP_REPO_URL "$BOOTSTRAP_REPO_URL"
  emit_env_kv BOOTSTRAP_REPO_BRANCH "$BOOTSTRAP_REPO_BRANCH"
  emit_env_kv BOOTSTRAP_REPO_DIR "$BOOTSTRAP_REPO_DIR"
  emit_env_kv AUTO_ACCEPT_DEFAULTS "$AUTO_ACCEPT_DEFAULTS"
  emit_env_kv AUTO_REBOOT "$AUTO_REBOOT"
  emit_env_kv LAMP_ID "$LAMP_ID"
  emit_env_kv LAMP_PORT "$LAMP_PORT"
  emit_env_kv MODE_SCRIPT "$MODE_SCRIPT"
  emit_env_kv MODEL_PROVIDER "$MODEL_PROVIDER"
  emit_env_kv MODEL_API_KEY "$MODEL_API_KEY"
  emit_env_kv MODEL_BASE_URL "$MODEL_BASE_URL"
  emit_env_kv MODEL_NAME "$MODEL_NAME"
  emit_env_kv MODEL_VOICE "$MODEL_VOICE"
  emit_env_kv RESPEAKER_VARIANT "$RESPEAKER_VARIANT"
  emit_env_kv INSTALL_LELAMP_SERVICE "$INSTALL_LELAMP_SERVICE"
  emit_env_kv INSTALL_OPENCLAW "$INSTALL_OPENCLAW"
  emit_env_kv OPENCLAW_INSTALL_MODE "$OPENCLAW_INSTALL_MODE"
  emit_env_kv INSTALL_TAILSCALE "$INSTALL_TAILSCALE"
  emit_env_kv RUN_OPENCLAW_ONBOARD "$RUN_OPENCLAW_ONBOARD"
  emit_env_kv RUN_DOWNLOAD_FILES_POSTBOOT "$RUN_DOWNLOAD_FILES_POSTBOOT"
  emit_env_kv LIVEKIT_URL "$LIVEKIT_URL"
  emit_env_kv LIVEKIT_API_KEY "$LIVEKIT_API_KEY"
  emit_env_kv LIVEKIT_API_SECRET "$LIVEKIT_API_SECRET"
} >"$BOOTSTRAP_ENV_PATH"

log "Writing firstrun.sh"
cat >"$FIRSTRUN_PATH" <<'EOF'
#!/usr/bin/env bash

set -euo pipefail

BOOTFS="/boot"
if [[ -d /boot/firmware && -f /boot/firmware/lelamp-bootstrap.env ]]; then
  BOOTFS="/boot/firmware"
fi

BOOTSTRAP_ENV="${BOOTFS}/lelamp-bootstrap.env"
AUTHORIZED_KEYS_STAGING="${BOOTFS}/lelamp-authorized_keys"
SYSTEM_BOOTSTRAP_DIR="/etc/lelamp"
SYSTEM_BOOTSTRAP_ENV="${SYSTEM_BOOTSTRAP_DIR}/lelamp-bootstrap.env"
BOOTSTRAP_SCRIPT="/usr/local/sbin/lelamp-bootstrap.sh"
BOOTSTRAP_SERVICE="/etc/systemd/system/lelamp-bootstrap.service"
BOOTSTRAP_DONE_MARKER="/var/lib/lelamp-bootstrap.done"

if [[ ! -f "$BOOTSTRAP_ENV" ]]; then
  echo "Missing bootstrap env at ${BOOTSTRAP_ENV}" >&2
  exit 1
fi

# shellcheck disable=SC1090
. "$BOOTSTRAP_ENV"

mkdir -p "$SYSTEM_BOOTSTRAP_DIR"
cp "$BOOTSTRAP_ENV" "$SYSTEM_BOOTSTRAP_ENV"
chmod 600 "$SYSTEM_BOOTSTRAP_ENV"

if [[ -n "${BOOTSTRAP_HOSTNAME:-}" ]]; then
  hostnamectl set-hostname "$BOOTSTRAP_HOSTNAME"
fi

systemctl enable ssh >/dev/null 2>&1 || true

if [[ -n "${BOOTSTRAP_WIFI_SSID:-}" && -n "${BOOTSTRAP_WIFI_PASSWORD:-}" ]]; then
  mkdir -p /etc/NetworkManager/system-connections
  cat >/etc/NetworkManager/system-connections/lelamp-bootstrap.nmconnection <<NMEOF
[connection]
id=${BOOTSTRAP_WIFI_SSID}
uuid=${BOOTSTRAP_WIFI_UUID}
type=wifi
autoconnect=true

[wifi]
mode=infrastructure
ssid=${BOOTSTRAP_WIFI_SSID}

[wifi-security]
auth-alg=open
key-mgmt=wpa-psk
psk=${BOOTSTRAP_WIFI_PASSWORD}

[ipv4]
method=auto

[ipv6]
addr-gen-mode=stable-privacy
method=auto

[proxy]
NMEOF
  chmod 600 /etc/NetworkManager/system-connections/lelamp-bootstrap.nmconnection
  if command -v raspi-config >/dev/null 2>&1; then
    raspi-config nonint do_wifi_country "${BOOTSTRAP_WIFI_COUNTRY:-CN}" || true
  fi
  systemctl restart NetworkManager >/dev/null 2>&1 || true
fi

if [[ -f "$AUTHORIZED_KEYS_STAGING" ]] && id "${BOOTSTRAP_USER}" >/dev/null 2>&1; then
  USER_HOME="$(getent passwd "${BOOTSTRAP_USER}" | cut -d: -f6)"
  install -d -m 700 -o "${BOOTSTRAP_USER}" -g "${BOOTSTRAP_USER}" "${USER_HOME}/.ssh"
  install -m 600 -o "${BOOTSTRAP_USER}" -g "${BOOTSTRAP_USER}" "$AUTHORIZED_KEYS_STAGING" "${USER_HOME}/.ssh/authorized_keys"
fi

cat >"$BOOTSTRAP_SCRIPT" <<'SCRIPTEOF'
#!/usr/bin/env bash

set -euo pipefail

BOOTSTRAP_ENV="/etc/lelamp/lelamp-bootstrap.env"
DONE_MARKER="/var/lib/lelamp-bootstrap.done"
LOG_FILE="/var/log/lelamp-bootstrap.log"

if [[ -f "$DONE_MARKER" ]]; then
  exit 0
fi

# shellcheck disable=SC1090
. "$BOOTSTRAP_ENV"

touch "$LOG_FILE"
chmod 644 "$LOG_FILE"
exec >>"$LOG_FILE" 2>&1

echo "==> $(date -u '+%Y-%m-%d %H:%M:%S UTC') zero-touch bootstrap starting"

wait_for_network() {
  local attempt

  for attempt in $(seq 1 30); do
    if curl -I -sSfL https://github.com >/dev/null 2>&1; then
      return 0
    fi
    sleep 10
  done

  echo "Network did not become ready in time" >&2
  return 1
}

wait_for_network

apt-get update
apt-get install -y ca-certificates curl git sudo

if ! id "${BOOTSTRAP_USER}" >/dev/null 2>&1; then
  echo "Bootstrap user ${BOOTSTRAP_USER} does not exist yet" >&2
  exit 1
fi

USER_HOME="$(getent passwd "${BOOTSTRAP_USER}" | cut -d: -f6)"
REPO_TARGET="${USER_HOME}/${BOOTSTRAP_REPO_DIR}"

if [[ -d "${REPO_TARGET}/.git" ]]; then
  su - "${BOOTSTRAP_USER}" -c "git -C '${REPO_TARGET}' fetch --all --prune"
  su - "${BOOTSTRAP_USER}" -c "git -C '${REPO_TARGET}' checkout '${BOOTSTRAP_REPO_BRANCH}'"
  su - "${BOOTSTRAP_USER}" -c "git -C '${REPO_TARGET}' pull --ff-only origin '${BOOTSTRAP_REPO_BRANCH}'"
else
  rm -rf "${REPO_TARGET}"
  su - "${BOOTSTRAP_USER}" -c "git clone --branch '${BOOTSTRAP_REPO_BRANCH}' --depth 1 '${BOOTSTRAP_REPO_URL}' '${REPO_TARGET}'"
fi

cd "${REPO_TARGET}/lelamp_runtime"

chmod +x \
  scripts/pi5_all_in_one.sh \
  scripts/pi_setup_max.sh \
  scripts/openclaw_pi5_setup.sh \
  scripts/install_openclaw_skill.sh \
  scripts/pi5_post_reboot_finalize.sh \
  scripts/lelamp_doctor.sh

su - "${BOOTSTRAP_USER}" -c "
  export AUTO_ACCEPT_DEFAULTS='${AUTO_ACCEPT_DEFAULTS}'
  export AUTO_REBOOT='${AUTO_REBOOT}'
  export LAMP_ID='${LAMP_ID}'
  export LAMP_PORT='${LAMP_PORT}'
  export MODE_SCRIPT='${MODE_SCRIPT}'
  export MODEL_PROVIDER='${MODEL_PROVIDER}'
  export MODEL_API_KEY='${MODEL_API_KEY}'
  export MODEL_BASE_URL='${MODEL_BASE_URL}'
  export MODEL_NAME='${MODEL_NAME}'
  export MODEL_VOICE='${MODEL_VOICE}'
  export RESPEAKER_VARIANT='${RESPEAKER_VARIANT}'
  export INSTALL_LELAMP_SERVICE='${INSTALL_LELAMP_SERVICE}'
  export INSTALL_OPENCLAW='${INSTALL_OPENCLAW}'
  export OPENCLAW_INSTALL_MODE='${OPENCLAW_INSTALL_MODE}'
  export INSTALL_TAILSCALE='${INSTALL_TAILSCALE}'
  export RUN_OPENCLAW_ONBOARD='${RUN_OPENCLAW_ONBOARD}'
  export RUN_DOWNLOAD_FILES_POSTBOOT='${RUN_DOWNLOAD_FILES_POSTBOOT}'
  export LIVEKIT_URL='${LIVEKIT_URL}'
  export LIVEKIT_API_KEY='${LIVEKIT_API_KEY}'
  export LIVEKIT_API_SECRET='${LIVEKIT_API_SECRET}'
  cd '${REPO_TARGET}/lelamp_runtime'
  ./scripts/pi5_all_in_one.sh
"

touch "$DONE_MARKER"
echo "==> $(date -u '+%Y-%m-%d %H:%M:%S UTC') zero-touch bootstrap finished"
SCRIPTEOF
chmod 755 "$BOOTSTRAP_SCRIPT"

cat >"$BOOTSTRAP_SERVICE" <<SERVICEEOF
[Unit]
Description=LeLamp zero-touch bootstrap
Wants=network-online.target
After=network-online.target
ConditionPathExists=!${BOOTSTRAP_DONE_MARKER}

[Service]
Type=oneshot
ExecStart=${BOOTSTRAP_SCRIPT}
RemainAfterExit=true
Restart=on-failure
RestartSec=20

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable lelamp-bootstrap.service

if [[ -f "${BOOTFS}/cmdline.txt" ]]; then
  sed -i 's# systemd.run=/boot/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target##g' "${BOOTFS}/cmdline.txt"
  sed -i 's# systemd.run=/boot/firmware/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target##g' "${BOOTFS}/cmdline.txt"
fi

rm -f "${BOOTFS}/firstrun.sh"
sync
EOF

chmod 755 "$FIRSTRUN_PATH"

log "Patching cmdline.txt for first boot execution"
patch_cmdline "$CMDLINE_PATH"

log "Boot partition seeded successfully"
cat <<EOF

Boot partition: ${BOOTFS_PATH}
Hostname: ${BOOTSTRAP_HOSTNAME}
User: ${BOOTSTRAP_USER}
Repo: ${BOOTSTRAP_REPO_URL} (${BOOTSTRAP_REPO_BRANCH})
Repo dir on Pi: ${BOOTSTRAP_REPO_DIR}
Wi-Fi configured: $([[ -n "$BOOTSTRAP_WIFI_SSID" ]] && printf 'yes' || printf 'no')
SSH key staged: $([[ -n "$BOOTSTRAP_SSH_PUBLIC_KEY" ]] && printf 'yes' || printf 'no')

Next boot behavior:
1. Pi creates the login user from userconf.txt
2. firstrun.sh sets hostname, SSH, optional Wi-Fi, and installs lelamp-bootstrap.service
3. lelamp-bootstrap.service clones ${BOOTSTRAP_REPO_URL}
4. Pi runs lelamp_runtime/scripts/pi5_all_in_one.sh unattended

You can now eject the card and boot the Pi.
EOF
