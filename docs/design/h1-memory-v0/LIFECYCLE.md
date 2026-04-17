# H1 Memory v0 — Lifecycle

## Session 的定义

一个 session = **一次 lelamp agent 进程的活跃寿命**，而不是"一次对话"。

- session 开始：`smooth_animation.py` 的 `entrypoint` **进入后的第一步**，在任何硬件 / arbiter 初始化**之前**；此时 writer 立刻做 "index 自检"（见下文）并写 `sessions/*.meta.json`
- session 结束：进程收到 `SIGTERM` / `SIGINT` / 正常退出时的 `atexit` 钩子
- session 之间的间隔（lelamp 没在跑）**不算** agent session

> **重要（与 H0 的解耦）**：session 开始 **不** 依赖 MotorBusServer 是否成功 `start()`。
> 即使 arbiter bind retry 失败、串口被占、`AnimationService.start()` 抛错，session 仍然正常开始；
> 这些硬件状态只影响 `meta.json` 里 `flags.motor_bus_enabled` 等字段，不影响 memory 层是否记录。
> 这保证了 "记忆层与硬件仲裁层独立" 的合同（见 `README.md` §"与 H0 的关系"）。

### 为什么是"一次进程"而不是"一次对话"

- lelamp 在 Pi 上是 systemd 常驻；一次物理坐到台灯前和下次坐，之间进程没重启 → 属于同一个 session
- "一次对话"的切分需要 VAD 语义 / 心跳超时；v0 不做这个判断，**物理进程边界就是最好的自然切分**
- 答辩场景：一次 demo 从开机到关机 = 一个 session，定义清晰好讲

### session_id 生成

```
sess_<YYYY-MM-DD>_<HH-MM-SS>          # agent 进程产出
sess_manual_<YYYY-MM-DD>_<HH-MM-SS>   # dashboard / remote_control 独立产出
例：sess_2026-04-17_23-11-15
例：sess_manual_2026-04-17_09-32-08
```

- 用本地时区；因为答辩现场演示时，用户的语义时间就是本地时间
- 精度到秒即可；同一秒启动两个进程是病态场景（systemd 不会这么干）
- `sess_manual_` 前缀专门用于区分"没有 agent 进程在跑"时由 dashboard / remote_control 产生的事件

---

## Agent session vs manual session —— dashboard / remote_control 的 session_id 归属

v0 的 session 概念是"**一次进程的活跃寿命**"；但 dashboard 和 `remote_control` 是**独立进程**，它们产生的 `playback` 事件也必须有 `session_id`（schema 强约束）。分三种场景，**规则显式**：

### 场景 A：agent 正在跑，dashboard / CLI 随附

最常见场景：`lelamp.service` 在跑，用户同时在 dashboard 或 terminal 里触发一个 `play`。

- dashboard / remote_control writer **依附**到 agent 当前 session：
  1. 扫 `sessions/*.meta.json` 按 `start_ts_ms` 降序
  2. 取最新那条，读 `pid` 字段，用 `os.kill(pid, 0)` 判活
  3. 进程存活 → 用它的 `session_id`（**不新建 manual session**）
- 写入时和 agent writer 走**同一把 flock**，不会冲突

这样 dashboard 点播的 playback 和 agent 本身记录的事件会并排出现在 `events.jsonl` 里，时间戳自然排序，答辩时一目了然。

### 场景 B：agent 没在跑，只有 dashboard / CLI

例如 `sudo systemctl stop lelamp`，然后 `python -m lelamp.remote_control play curious` 做单独硬件调试。

- dashboard / remote_control writer 检测不到存活 agent session → **新建一个 manual session**：
  - `session_id = sess_manual_<YYYY-MM-DD>_<HH-MM-SS>`
  - 写 `sessions/<session_id>.meta.json`：

    ```json
    {
      "schema": "lelamp.memory.v0.session_meta",
      "session_id": "sess_manual_2026-04-17_09-32-08",
      "user_id": "default",
      "start_ts_ms": 1776432728000,
      "start_ts_iso": "2026-04-17T09:32:08+08:00",
      "timezone": "Asia/Shanghai",
      "pid": null,
      "git_ref": null,
      "model_providers": [],
      "flags": {
        "motor_bus_enabled": false,
        "fluxchi_enabled": false,
        "source": "standalone_writer"
      }
    }
    ```

  - `pid=null` 和 `flags.source="standalone_writer"` 是 manual session 的**区分标记**，summary / recent_index 生成时可以选择性排除
- manual session 的 `summary.json` 在**下一个任意 writer 启动自检**里补写（writer 自检发现"有 meta 无 summary"→ 扫事件补 summary，对 manual session 同样适用）

### 场景 C：dashboard 和 CLI 同时并发，都没有 agent

极少见。两个独立进程都尝试新建 manual session。由 **flock 串行化**决定：先拿锁的那个写 meta.json，后拿锁的读到 meta 存活（秒级 ts 差距 < 1s）→ 依附到它。**同一秒启动是病态场景**，与 agent session 的同名冲突规则一致（见 `OPEN_QUESTIONS.md` OQ-2）。

### 归属判活的小工具函数（规格）

writer 模块必须提供一个纯函数：

```
attach_or_create_session() -> (session_id, is_manual)
  1. 扫 sessions/*.meta.json，按 start_ts_ms 降序
  2. 逐条：pid 非空且存活？→ 返回 (session_id, False)
  3. 扫完没找到 → 分配 sess_manual_<ts>，写 meta，返回 (session_id, True)
  操作全程在 flock 保护下
```

所有 dashboard / remote_control 的事件写入**必须**走这个函数拿到的 `session_id`，不得自造。

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
manual session 的 meta 结构相同，只是 `pid=null` + `flags.source="standalone_writer"`（见上文"场景 B"）。

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
- **manual session 不生成 `narrative`**（没有对话脉络可总结），只写统计字段

### 为什么 summary 不是事件

因为它是**派生**的。events 是 ground truth，summary 是 cache；任何时候都能从 events.jsonl 重建 summary。所以 summary 丢了不是 corruption，只是需要重新扫一遍事件。

---

## Recent Window（最近窗口）

prompt 注入要"带最近一点上下文"。v0 的窗口定义：

```
最近 3 个 agent session，且 |events_considered| ≤ 200
取两个条件交集里更严格的那个
```

- **manual session 默认不进 recent window**（它们是调试 / 硬件测试产物，不代表用户语境）
- 但 manual session 的事件仍会在 `events.jsonl` 里、在归档里；只是 `recent_index.json` 只索引 agent session 的 summary

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

- `sessions`：列出最近 3 个 **agent** session 的 summary 指针（过滤掉 `sess_manual_` 前缀）
- `event_tail_refs`：最近 200 个事件的**索引**（仅 `event_id` + `kind` + `ts_ms`）；reader 按需回读全文

选择 `session_count_cap = 3` 和 `event_cap = 200` 的理由：

- 3 session = 大约最近 1 周的日常使用（答辩视角足够）
- 200 事件 ≈ 50 轮对话（每轮 4 事件），塞进 512 tokens 预算里裁剪得动
- 取 min 是为了**双向兜底**：短 session × 很多次 和 长 session × 少数次，都不会爆预算

**重建时机（只由 writer 负责）**：

- session 结束写 `summary.json` 的同一步骤后立即重建 `recent_index.json`
- 下次 session 启动时 **writer** 先做一次 "index 自检"（在写 `meta.json` **之前**，flock 保护下）：
  - `recent_index.json` 缺失 / `built_at_ms` 早于 `events.jsonl` 的 mtime → writer 同步重建一次
  - 存在 `sessions/*.meta.json` 但缺对应 `summary.json`（说明上次崩了）→ writer 扫残余 events 补一份 summary（对 agent session 和 manual session 都适用）
- 重建原子：tmp+rename

> **Reader 永不参与重建**。这和 `PROMPT_INTEGRATION.md` §"Reader 的副作用契约" 一致：
> prompt_builder 在读取时若发现 `recent_index.json` 缺失 / 过期，直接走**降级读**（扫最多 3 个最近的 agent `sessions/*.summary.json`），**不写盘**。
> 任何 "修盘" 路径只出现在 **writer 进程的启动自检** 里，且在写 `meta.json` 之前完成。

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

- session 结束写 summary 失败 → 下次 **writer** 启动自检时扫残留 events **回填**
- recent_index 缺 / 过期 → 下次 **writer** 启动自检时重建
- 所有恢复路径**可重入**、**幂等**
- **Reader 不参与任何修复**；遇到缺失 / 过期 → 降级读（扫最多 3 个最近 agent `sessions/*.summary.json`），不写盘

> 为什么把修复收编到 writer：reader 并发度高（每次 session 启动的 prompt 构建）且常被打包进同步路径；让 reader 写盘 = 潜在多进程写冲突 + 把延迟引进 agent 启动。writer 自检是**单次、串行、在 flock 保护下**完成的，语义干净。

### Manual session 孤儿

- dashboard / remote_control 新建了 manual session 后崩溃 → `meta.json` 存在但 `summary.json` 缺失
- 下一个**任意** writer 启动时（agent writer 或另一个 manual writer）做自检，按"存在 meta 无 summary"路径补 summary
- Manual session 的 summary 不进 `recent_index`，所以即使短暂缺失也不影响 prompt 注入

### 时间倒流（用户手工改系统时钟）

- writer 端检测到 `ts_ms < last_ts_ms - 5min` → 打 WARN，但仍然按当前时钟写
- v0 不试图修正；答辩不会遇到

### profile.json 被手工编辑坏了

- reader 端 `json.JSONDecodeError` → 退化到"无 profile"模式，整个 memory 还能用
- `display_name` / `banned_styles` 等影响 prompt 层，但不影响 writer

---

## 时间线示例

### 场景 1：正常 agent 生命周期

```
T=0s     Pi 开机，systemd 起 lelamp.service
T=0.2s   smooth_animation entrypoint 进入
         writer 启动自检（flock 下）:
           - 若上次 agent 或 manual session 有 meta 无 summary → 补写
           - 若 recent_index.json 缺失/过期 → 扫最近 3 个 agent summary 重建
         writer 写 sessions/sess_...meta.json（tmp+rename）
         writer 开启 events.jsonl append-only fd
T=0.4s   MotorBusServer.start() 尝试 bind（可能成功，可能 bind retry 最终失败）
         无论成败，meta.json 里 flags.motor_bus_enabled 已记录真实状态
T=2s     用户说"你好"；ASR commit → LLM response → 1 条 conversation 事件
         AutoExpression 350ms 到点前 LLM 调了 express("caring") → function_tool x2
         RGB 没变 → 0 条 playback
...
T=2h     systemctl restart lelamp
T=2h+0s  atexit:
           - writer 扫本 session events → 写 sessions/sess_..._summary.json
           - 重算 recent_index.json（manual session 不入）
           - 释放文件锁
T=2h+1s  新进程启动，重复 T=0.2 流程（writer 自检 → meta → arbiter）
```

### 场景 2：只有 dashboard / CLI，agent 不在

```
T=0s     sudo systemctl stop lelamp
T=10s    用户在 terminal 执行: python -m lelamp.remote_control play curious
T=10.0s  remote_control writer 调 attach_or_create_session():
           - 扫 sessions/*.meta.json 降序，发现最新 agent session 的 pid 不存活
           - 新建 sess_manual_2026-04-17_09-32-10
           - 写 manual meta.json（pid=null，flags.source=standalone_writer）
T=10.1s  remote_control 调 build_rgb_service_with_proxy / build_animation_service_with_proxy
         motor_bus sentinel 不存在 → 走 direct fallback（H0 语义）
T=12s    play 完成，remote_control writer 写一条 playback(initiator=remote_control,
         session_id=sess_manual_...)，进程退出
         （不在 atexit 立刻写 summary——remote_control 是短命进程，
          summary 由下次任意 writer 启动自检补）
T=1h     sudo systemctl start lelamp
T=1h+0.2s 新 agent writer 自检发现 sess_manual_... 有 meta 无 summary
         → 扫残余 events 补 summary（只含 1 条 playback）
         → recent_index.json 重建时**不包含**这条 manual session
```
