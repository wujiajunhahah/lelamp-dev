# H0 Final Pi Acceptance Report

**Date**: 2026-04-18 00:43–00:51 CST  
**Target Pi**: `raspberrypi.local` (`172.20.10.2`), user `wujiajun`  
**Deployed commit**: `2f51247` (`fix(motor_bus): arm playback gate before dispatch and retry port bind`)  
**Branch**: `feature/motor-bus-arbiter`  
**Verification method**: deployed-file MD5 match against local `git show 2f51247:lelamp/motor_bus/server.py`  
→ **`9ace4509954ee7e79399caa5101c8318`** on both, confirmed identical.

---

## Acceptance Matrix

| # | Item | Result | Evidence |
|---|---|---|---|
| 1 | Deployed version matches `2f51247` | ✅ PASS | MD5 `9ace4509...c8318` 与 `git show 2f51247:.../server.py` 完全一致 |
| 2 | Sentinel + domain-aware Health | ✅ PASS | `/tmp/lelamp-motor-bus.json` 正确写入；`/health` 返回 `ok/motor_ok/rgb_ok/rgb_available/led_count/pid` 全域 |
| 3 | `_arm_playback_gate` race fix | ✅ PASS | 连续 play #1/#2 间隔 13ms；`wait_complete(timeout=25)` **真实阻塞 12.218s** 才返回 `done=true` |
| 4 | `bind_retry` cold-restart | ❌ **FAIL** | 见 "发现的 bug" |
| 5 | Dashboard busy lock | ✅ PASS | play(curious) 后 t=+1~11s 持续 `running`, t=+12s 准确释放到 `ready`, 总时长 12.253s |
| 6 | CLI fallback when MotorBus dead | ✅ PASS | `systemctl stop` 后 `remote_control play curious` 直接 `/dev/ttyACM0`, 全程 16s, exit 0 |

**4 / 6 通过，1 非阻塞 PASS，1 需 H0.3 修复。**

---

## 发现的 bug: `_port_is_free` 未用 `SO_REUSEADDR`

### 症状
```
00:43:50 INFO  motor bus port 127.0.0.1:8770 busy; retrying bind for up to 12.0s
00:44:02 WARN  motor bus port 127.0.0.1:8770 is busy; server not started (waited 12.0s)
00:44:02 WARN  __main__  motor bus server failed to start; dashboard/CLI will contend for hardware
```

### 根因
`lelamp/motor_bus/server.py` L178-184：

```python
def _port_is_free(host: str, port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        try:
            sock.bind((host, port))     # ← 没设 SO_REUSEADDR
        except OSError:
            return False
    return True
```

- probe socket 没有 `SO_REUSEADDR`，遇到 TIME_WAIT 态端口会 `EADDRINUSE`
- Linux 默认 `tcp_fin_timeout=60s`，12s retry 窗口根本不够
- 真正的 uvicorn 启动时 *会* 开 `SO_REUSEADDR` (uvicorn 默认)，probe 和真实 bind 行为不一致导致白白放弃

### 建议修复（H0.3）
```python
def _port_is_free(host: str, port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True
```

同时建议延长 `bind_retry_total_s` 默认值到 **30s**（给 `SO_REUSEADDR` 都穿不过的极端场景留裕度），并在 retry 失败时日志记录 kernel-reported error code 便于后续诊断。

### 影响面
- 仅影响 **快速连续 systemctl restart** 场景（间隔 < 60s）
- 单次正常冷启动不受影响
- 失败时 runtime 正确 fallback 到 "dashboard/CLI contend for hardware"（不崩溃、不 regress，只是 H0 arbiter 暂时失效）

### 何时修
- **不阻塞** H1 memory v0 设计稿 PR (已开 https://github.com/wujiajunhahah/lelamp-dev/pull/1)
- **阻塞** `feature/motor-bus-arbiter` → `runtime-main` 合并（H0 的核心价值就是仲裁，bind retry 失败等于 arbiter 空转）
- 建议 H0.3 作为 `feature/motor-bus-arbiter` 的最后一个 commit

---

## 次要观察（非阻塞）

**`MotorBusServer.stop()` 的 sentinel cleanup 在 `systemctl stop` 路径下不触发**

- `/tmp/lelamp-motor-bus.json` 在 service 停止后依然存在（pid 指向已死进程）
- 客户端通过 HTTP `/health` 探活，stale sentinel **不会**造成误判（这次 remote_control 成功 fallback 即为证据）
- 若想收紧，可在 `MotorBusServer` 构造时注册 `atexit` / signal handler
- **不建议**在 H0 范围内修，优先级低

---

## 当前 Pi 状态（报告生成时）

- `lelamp.service`: active  
- `MotorBusServer`: 未绑定（受 bind retry bug 影响）  
- dashboard `:8765`: healthy (`status=ready`)  
- 硬件直连路径：可用（dashboard/CLI 会 direct-contention，H0 arbiter 暂时离线）  
- 等 TIME_WAIT 完全过期（约 60s）后下一次 systemctl restart 会恢复正常 arbiter  

---

## 结论

1. **H0 的核心修复 (`_arm_playback_gate` + completion wait + domain-aware health) 全部通过 Pi 实机验收**
2. **`bind retry` 发现一个边界 bug，记录为 H0.3 待修项**，不影响已开的 H1 design PR
3. **不建议**当前状态合并 `feature/motor-bus-arbiter` → `runtime-main`；先补 H0.3 再合
