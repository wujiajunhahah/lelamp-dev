# H1 Memory v0 — Lifecycle

## Session 的定义

一个 session = **一次 lelamp agent 进程的活跃寿命**，而不是"一次对话"。

- session 开始：`smooth_animation.py` 的 `entrypoint` 里，MotorBusServer 成功 `start()` 之后 1 步
- session 结束：进程收到 `SIGTERM` / `SIGINT` / 正常退出时的 `atexit` 钩子
- session 之间的间隔（lelamp 没在跑）**不算** session

### 为什么是"一次进程"而不是"一次对话"

- lelamp 在 Pi 上是 systemd 常驻；一次物理坐到台灯前和下次坐，之间进程没重启 → 属于同一个 session
- "一次对话"的切分需要 VAD 语义 / 心跳超时；v0 不做这个判断，**物理进程边界就是最好的自然切分**
- 答辩场景：一次 demo 从开机到关机 = 一个 session，定义清晰好讲

### session_id 生成

```
sess_<YYYY-MM-DD>_<HH-MM-SS>
例：sess_2026-04-17_23-11-15
```

- 用本地时区；因为答辩现场演示时，用户的语义时间就是本地时间
- 精度到秒即可；同一秒启动两个进程是病态场景（systemd 不会这么干）

---

## Session 生命周期中的三种文件

```
sessions/sess_2026-04-17_23-11-15.meta.json         # session 开始时写
sessions/sess_2026-04-17_23-11-15.summary.json      # session 结束时写
events.jsonl                                        # 整个 session 的事件 inline
```

### `*.meta.json`

Session 启动那一刻写入，**原子**（tmp+rename）：

```json
{
  "schema": "lelamp.memory.v0.session_meta",
  "session_id": "sess_2026-04-17_23-11-15",
  "user_id": "default",
  "start_ts_ms": 1776438675000,
  "start_ts_iso": "2026-04-17T23:11:15+08:00",
  "timezone": "Asia/Shanghai",
  "pid": 9551,
  "git_ref": "cf5a692",
  "model_providers": ["qwen"],
  "flags": {
    "motor_bus_enabled": true,
    "fluxchi_enabled": false
  }
}
```

`timezone`：写 IANA 名字，供日后跨时区 replay 用。

### `*.summary.json`

Session 结束时写入（`atexit` 触发），**原子**：

```json
{
  "schema": "lelamp.memory.v0.session_summary",
  "session_id": "sess_2026-04-17_23-11-15",
  "start_ts_ms": 1776438675000,
  "end_ts_ms": 1776450123000,
  "duration_s": 11448,
  "event_counts": {
    "conversation": 42,
    "function_tool": 57,
    "fallback_expression": 19,
    "playback": 34
  },
  "style_histogram": {
    "excited": 12,
    "caring": 18,
    "worried": 6,
    "sad": 3
  },
  "fallback_rate": 0.33,
  "top_recordings": ["curious", "happy_wiggle", "shy"],
  "narrative": "本次会话持续 3 小时 10 分，用户多以 caring 风格被回应；…"
}
```

字段说明：

- `event_counts`、`style_histogram`、`fallback_rate`、`top_recordings` 都是**纯统计**，由 writer 在进程退出前扫本 session 的 events 计算
- `fallback_rate` = `fallback_expression` 事件数 / `conversation` 事件数；= 0.33 意味着每 3 轮对话就有 1 次被 AutoExpressionController 兜底
- `narrative` 是**可选**的自然语言摘要；v0 的生产策略：
  - **默认不生成**，值为 `null`
  - 可选生成，由一个独立的 summarization 步骤（本地 Gemma-3-4B-GGUF 或者 qwen 短 prompt）产出
  - 生成失败 / 超时 → 依然写 summary，`narrative = null`，不阻塞 session 正常退出
- **narrative 预算上限：512 tokens / 1024 字符**；超出截断

### 为什么 summary 不是事件

因为它是**派生**的。events 是 ground truth，summary 是 cache；任何时候都能从 events.jsonl 重建 summary。所以 summary 丢了不是 corruption，只是需要重新扫一遍事件。

---

## Recent Window（最近窗口）

prompt 注入要"带最近一点上下文"。v0 的窗口定义：

```
最近 3 个 session，且 |events_considered| ≤ 200
取两个条件交集里更严格的那个
```

落地文件：`recent_index.json`（每个 session 结束时重算）：

```json
{
  "schema": "lelamp.memory.v0.recent_index",
  "built_at_ms": 1776450123500,
  "sessions": [
    { "session_id": "sess_2026-04-17_23-11-15", "summary_ref": "sessions/sess_2026-04-17_23-11-15.summary.json" },
    { "session_id": "sess_2026-04-16_20-02-41", "summary_ref": "sessions/sess_2026-04-16_20-02-41.summary.json" },
    { "session_id": "sess_2026-04-15_19-51-03", "summary_ref": "sessions/sess_2026-04-15_19-51-03.summary.json" }
  ],
  "event_tail_refs": [
    { "event_id": "01JR5K...", "kind": "conversation", "ts_ms": 1776449001000 }
  ]
}
```

- `sessions`：列出最近 3 个 session 的 summary 指针（避免反复加载全量事件）
- `event_tail_refs`：最近 200 个事件的**索引**（仅 `event_id` + `kind` + `ts_ms`）；reader 按需回读全文

选择 `session_count_cap = 3` 和 `event_cap = 200` 的理由：

- 3 session = 大约最近 1 周的日常使用（答辩视角足够）
- 200 事件 ≈ 50 轮对话（每轮 4 事件），塞进 512 tokens 预算里裁剪得动
- 取 min 是为了**双向兜底**：短 session × 很多次 和 长 session × 少数次，都不会爆预算

**重建时机**：

- session 结束写 `summary.json` 的同一步骤后立即重建 `recent_index.json`
- writer 崩溃 → 下次 session 启动时 reader 发现 `recent_index.json` 的 `built_at_ms` 老于 `events.jsonl` 的 mtime，**自动重建一次**
- 重建原子：tmp+rename

---

## 归档（Archive）

### 触发条件

下列**任一**成立就触发 rotate：

- `events.jsonl` 体积 > **10 MiB**
- `events.jsonl` 的 `ts_ms` 跨度 > **3 天**
- 手工：`python -m lelamp.memory.rotate`（未来实现留口子）

### 归档流程

```
1. flock 锁住全局锁
2. 按月聚合：把本 events.jsonl 里所有事件按 ts_ms 的 YYYY-MM append 到 archive/YYYY-MM.jsonl
3. 原子清空 events.jsonl（tmp/empty → rename）
4. 在 archive/ 里写 _MANIFEST.json：记录每个月份文件的事件计数、起止时间、MD5
5. 释放锁
```

### 不可丢

- **不删除**任何事件。v0 的立场是"硬盘便宜、记忆珍贵"
- 真要删 → 用户自己 `rm`；程序不提供删除 API

### archive 的 reader 契约

- prompt 注入层**不读**归档，只读 `events.jsonl` 的尾部 + `recent_index.json`
- 归档文件是**审计存档**，给用户 `grep / jq` 用，不是在线路径
- 后续如果做"长程记忆"（v1+），会在读路径加一个 retrieval 层；v0 没有

---

## 老化规则（Decay）

v0 **不主动衰减**（不 downweight、不 merge 旧 session 的 summary）。

理由：

- 衰减意味着有"权重模型"，进入策略层，违背 v0 的硬边界
- `recent_index.json` 的 cap = 3 session 自然实现了"只看近期"
- 更老的 session 依然在 `sessions/*.summary.json` 里，想看的时候可以 `ls -lt sessions/` 翻

---

## 容错与恢复

### events.jsonl 末行损坏

- reader 在解析时 `json.JSONDecodeError` on last line → 跳过、继续
- writer 下次 append 时前置一个 `\n`（若上一行没以 `\n` 结尾）

### summary / recent_index 缺失

- session 结束写 summary 失败 → 下次 reader 启动时扫 events.jsonl **回填**
- recent_index 缺 → reader 扫最近 N 个 summary **重建**
- 所有恢复路径**可重入**、**幂等**

### 时间倒流（用户手工改系统时钟）

- writer 端检测到 `ts_ms < last_ts_ms - 5min` → 打 WARN，但仍然按当前时钟写
- v0 不试图修正；答辩不会遇到

### profile.json 被手工编辑坏了

- reader 端 `json.JSONDecodeError` → 退化到"无 profile"模式，整个 memory 还能用
- `display_name` / `banned_styles` 等影响 prompt 层，但不影响 writer

---

## 时间线示例

```
T=0s     Pi 开机，systemd 起 lelamp.service
T=0.3s   smooth_animation entrypoint → MotorBusServer started
T=0.4s   writer 写 sessions/sess_...meta.json（tmp+rename）
         writer 开启 events.jsonl append-only fd
T=2s     用户说"你好"；ASR commit → LLM response → 1 条 conversation 事件
         AutoExpression 350ms 到点前 LLM 调了 express("caring") → function_tool x2
         RGB 没变 → 0 条 playback
...
T=2h     systemctl restart lelamp
T=2h+0s  atexit:
           - writer 扫本 session events → 写 sessions/sess_..._summary.json
           - 重算 recent_index.json
           - 释放文件锁
T=2h+1s  新进程启动，session_id 变化，重复 T=0.3 流程
```

