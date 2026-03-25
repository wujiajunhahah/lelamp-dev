#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_SRC="${REPO_ROOT}/openclaw/skills/lelamp-control/SKILL.md"
OPENCLAW_SKILL_HOME="${OPENCLAW_SKILL_HOME:-$HOME/.openclaw/skills}"
SKILL_DEST="${OPENCLAW_SKILL_HOME}/lelamp-control"

mkdir -p "${SKILL_DEST}"
cp "${SKILL_SRC}" "${SKILL_DEST}/SKILL.md"

printf 'Installed LeLamp OpenClaw skill to %s\n' "${SKILL_DEST}"
