# Pi Connectivity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-first Raspberry Pi resolver with Tailscale fallback, plus a headless Tailscale setup flow that auto-reconnects whenever the Pi regains network.

**Architecture:** Keep host discovery in one reusable shell script so sync and future maintenance commands share the same target-resolution logic. Add a separate remote Tailscale bootstrap script that installs `tailscaled`, enables it at boot, and optionally performs the first `tailscale up --ssh` with an auth key for fully headless setup.

**Tech Stack:** Bash, Python `unittest`, existing SSH/rsync-based maintenance scripts.

---

### Task 1: Lock down host resolution behavior

**Files:**
- Create: `lelamp_runtime/lelamp/test/test_resolve_pi_host_script.py`
- Modify: `lelamp_runtime/lelamp/test/test_sync_pi_runtime_script.py`
- Modify: `lelamp_runtime/scripts/sync_pi_runtime.sh`

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run the sync/resolver script tests and confirm the new resolver integration fails**
- [ ] **Step 3: Update `sync_pi_runtime.sh` to resolve the target via `scripts/resolve_pi_host.sh`**
- [ ] **Step 4: Re-run the script tests and confirm they pass**

### Task 2: Add headless Tailscale bootstrap

**Files:**
- Create: `lelamp_runtime/scripts/setup_tailscale_remote.sh`
- Create: `lelamp_runtime/lelamp/test/test_setup_tailscale_remote_script.py`

- [ ] **Step 1: Write the failing Tailscale setup script test**
- [ ] **Step 2: Run the new test and confirm it fails because the script does not exist yet**
- [ ] **Step 3: Implement remote install + enable/start + optional auth-key registration**
- [ ] **Step 4: Re-run the Tailscale setup test and confirm it passes**

### Task 3: Document the workflow

**Files:**
- Modify: `lelamp_runtime/README.md`
- Modify: `README.md`

- [ ] **Step 1: Document local-first Pi discovery with Tailscale fallback**
- [ ] **Step 2: Document first-time headless Tailscale setup and the “online means auto-reconnect” behavior**
- [ ] **Step 3: Document the new environment variables and example commands**

### Task 4: Final verification and integration

**Files:**
- Modify: `lelamp_runtime/scripts/openclaw_pi5_setup.sh` (only if the Tailscale env handoff can be added safely)

- [ ] **Step 1: Run the focused script test suite**
- [ ] **Step 2: If the existing installer can safely inherit the same Tailscale env, wire it in**
- [ ] **Step 3: Re-run verification after any installer change**
- [ ] **Step 4: Commit and push to `main`**
