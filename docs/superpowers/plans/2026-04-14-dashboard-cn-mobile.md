# LeLamp Dashboard CN Mobile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把本地 LeLamp dashboard 改成中文、展台演示感、手机端先看状态的展示层，同时保持现有 API 与诚实降级行为不变。

**Architecture:** 只改 `lelamp/dashboard/web/` 和其对应前端测试。HTML 重排信息层级，CSS 重做桌面与手机端的视觉和布局，JS 增加中文文案与状态映射，后端接口与 action contract 不变。

**Tech Stack:** 静态 HTML, CSS, 原生 JavaScript, Python `unittest`, Node VM-based frontend test harness

---

### Task 1: 锁定前端展示契约

**Files:**
- Modify: `lelamp/test/test_dashboard_web.py`

- [ ] **Step 1: 写失败测试，断言中文首页结构和核心文案**

```python
def test_index_contains_chinese_showcase_regions(self) -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")

    self.assertIn("本地展台", html)
    self.assertIn("当前状态", html)
    self.assertIn("动作控制", html)
    self.assertIn("现场信息", html)
```

- [ ] **Step 2: 运行单测确认它先失败**

Run: `python3 -m unittest lelamp.test.test_dashboard_web.DashboardWebTests.test_index_contains_chinese_showcase_regions -v`
Expected: FAIL because current HTML still uses English copy.

- [ ] **Step 3: 写失败测试，锁定手机端新的布局类名和断点**

```python
def test_dashboard_css_contains_mobile_showcase_rules(self) -> None:
    css = (ROOT / "dashboard.css").read_text(encoding="utf-8")

    self.assertIn("@media (max-width: 760px)", css)
    self.assertIn(".hero-panel", css)
    self.assertIn(".details-grid", css)
    self.assertIn("grid-template-columns: 1fr;", css)
```

- [ ] **Step 4: 运行单测确认它先失败或至少锁到新增契约**

Run: `python3 -m unittest lelamp.test.test_dashboard_web.DashboardWebTests.test_dashboard_css_contains_mobile_showcase_rules -v`
Expected: FAIL until new CSS contract is added.

- [ ] **Step 5: 写失败测试，锁定 JS 的中文标签与状态映射**

```python
self.assertEqual(payload["startupLabel"], "启动灯")
self.assertEqual(payload["motionStatus"], "醒着")
```

- [ ] **Step 6: 运行 JS harness 单测确认它先失败**

Run: `python3 -m unittest lelamp.test.test_dashboard_web.DashboardWebTests.test_dashboard_js_renders_chinese_labels_and_motion_copy -v`
Expected: FAIL because current script still renders English labels and raw status strings.

- [ ] **Step 7: Commit**

```bash
git add lelamp/test/test_dashboard_web.py
git commit -m "test: lock dashboard chinese mobile ui contract"
```

### Task 2: 实现中文展台首页和手机端适配

**Files:**
- Modify: `lelamp/dashboard/web/index.html`
- Modify: `lelamp/dashboard/web/dashboard.css`
- Modify: `lelamp/dashboard/web/dashboard.js`
- Modify: `lelamp/test/test_dashboard_web.py`

- [ ] **Step 1: 修改 HTML，把页面分成“当前状态 / 动作控制 / 现场信息”三层**

```html
<h1>LeLamp 本地展台</h1>
<section class="hero-panel">...</section>
<section class="panel panel--actions">...</section>
<section id="diagnosticsPanel" class="panel panel--details">...</section>
```

- [ ] **Step 2: 修改 CSS，强化 hero 区并让手机端改成单列状态优先**

```css
.hero-panel { ... }
.hero-status-grid { ... }
.details-grid { ... }

@media (max-width: 760px) {
  .layout,
  .hero-grid,
  .hero-status-grid,
  .details-grid,
  .control-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 3: 修改 JS，加入中文按钮标签、状态翻译和演示文案**

```javascript
var ACTION_META = {
  startupButton: { actionKey: "startup", baseClass: "...", label: "启动灯" },
};

function translateMotionStatus(status) {
  if (status === "idle") return "醒着";
  if (status === "running") return "动作中";
  if (status === "homing") return "回位中";
  if (status === "error") return "需要检查";
  return "未连接";
}
```

- [ ] **Step 4: 运行 dashboard 前端测试，确认全部通过**

Run: `python3 -m unittest lelamp.test.test_dashboard_web -v`
Expected: PASS

- [ ] **Step 5: 运行更完整的 dashboard 套件，确认未破坏 API/状态契约**

Run: `python3 -m unittest lelamp.test.test_dashboard_actions lelamp.test.test_dashboard_api lelamp.test.test_dashboard_samplers lelamp.test.test_dashboard_web -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add lelamp/dashboard/web/index.html lelamp/dashboard/web/dashboard.css lelamp/dashboard/web/dashboard.js lelamp/test/test_dashboard_web.py
git commit -m "feat: localize dashboard for chinese mobile demos"
```

### Task 3: 同步文档与远端分支

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-04-14-dashboard-cn-mobile-design.md`
- Modify: `docs/superpowers/plans/2026-04-14-dashboard-cn-mobile.md`

- [ ] **Step 1: 如有必要补充 README 的 dashboard 文案**

```markdown
- Dashboard 默认使用中文展台式界面，适合 Pi 本地屏幕和手机端演示。
```

- [ ] **Step 2: 运行 `git status --short` 检查只包含预期改动**

Run: `git status --short`
Expected: only dashboard/web, tests, docs, and optional README updates.

- [ ] **Step 3: 推送到远端特性分支**

Run: `git push -u origin feature/dashboard-cn-mobile`
Expected: branch published successfully.
