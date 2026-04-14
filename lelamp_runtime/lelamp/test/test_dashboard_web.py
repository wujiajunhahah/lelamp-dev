import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "dashboard" / "web"


class DashboardWebTests(unittest.TestCase):
    def test_index_contains_chinese_showcase_regions(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("LeLamp 本地展台", html)
        self.assertIn("当前状态", html)
        self.assertIn("动作控制", html)
        self.assertIn("现场信息", html)
        self.assertIn('id="connectionStatus"', html)
        self.assertIn('id="systemStatus"', html)
        self.assertIn('id="startupButton"', html)
        self.assertIn('id="shutdownPoseButton"', html)
        self.assertIn('id="diagnosticsPanel"', html)
        self.assertIn('id="recordingList"', html)
        self.assertIn('id="hardwareNotes"', html)
        self.assertIn('id="connectivityHints"', html)
        self.assertIn('id="configSnippets"', html)

    def test_dashboard_css_contains_mobile_showcase_rules(self) -> None:
        css = (ROOT / "dashboard.css").read_text(encoding="utf-8")

        self.assertIn("@media (max-width: 1120px)", css)
        self.assertIn("@media (max-width: 760px)", css)
        self.assertIn(".hero-panel", css)
        self.assertIn(".hero-status-grid", css)
        self.assertIn(".details-grid", css)
        self.assertIn("grid-template-columns: 1fr;", css)

    def test_dashboard_js_starts_polling_at_400ms(self) -> None:
        source_path = ROOT / "dashboard.js"
        script = f"""
const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync({json.dumps(str(source_path))}, "utf8");
const pollCalls = [];
const nodes = {{}};

function createNode(id) {{
  return {{
    id,
    textContent: "",
    disabled: false,
    value: "",
    innerHTML: "",
    children: [],
    addEventListener: function () {{}},
    appendChild: function (child) {{
      this.children.push(child);
      if (typeof child.value !== "undefined") {{
        this.value = child.value;
      }}
    }},
  }};
}}

const context = {{
  console,
  Promise,
  JSON,
  setTimeout,
  clearTimeout,
}};

context.fetch = function (url) {{
  pollCalls.push(url);
  if (url === "/api/actions") {{
    return Promise.resolve({{
      json: function () {{
        return Promise.resolve({{
          busy: false,
          recordings: ["curious"],
          poll_ms: 400,
          actions: {{
            startup: {{ enabled: true, state: "enabled", label: "启动灯" }},
            play: {{ enabled: true, state: "enabled", label: "播放动作" }},
            stop: {{ enabled: true, state: "enabled", label: "回到待机" }},
            shutdown_pose: {{ enabled: true, state: "enabled", label: "进入休息" }},
            light_solid: {{ enabled: true, state: "enabled", label: "暖黄灯光" }},
            light_clear: {{ enabled: true, state: "enabled", label: "关闭灯光" }},
          }},
        }});
      }},
    }});
  }}

  return Promise.resolve({{
    json: function () {{
      return Promise.resolve({{
        system: {{ status: "ready", active_action: null, last_update_ms: 0, reachable_urls: [] }},
        motion: {{ status: "idle", available_recordings: ["curious"] }},
        light: {{ status: "off" }},
        audio: {{ status: "ready" }},
        errors: [],
      }});
    }},
  }});
}};

context.window = {{
  intervalMs: null,
  setInterval: function (_fn, ms) {{
    this.intervalMs = ms;
  }},
  addEventListener: function () {{}},
  fetch: null,
}};

context.document = {{
  getElementById: function (id) {{
    if (!nodes[id]) {{
      nodes[id] = createNode(id);
    }}
    return nodes[id];
  }},
  createElement: function () {{
    return createNode("option");
  }},
}};

context.window.fetch = context.fetch;
vm.createContext(context);
vm.runInContext(source, context);

Promise.resolve(context.DashboardApp.start(context.document, context.window, context.fetch, 400))
  .then(function () {{
    console.log(JSON.stringify({{
      intervalMs: context.window.intervalMs,
      pollCalls,
      startupLabel: nodes.startupButton.textContent,
      motionStatus: nodes.motionStatus.textContent,
    }}));
  }})
  .catch(function (error) {{
    console.error(error && error.stack ? error.stack : String(error));
    process.exit(1);
  }});
"""

        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout.strip())
        self.assertEqual(payload["intervalMs"], 400)
        self.assertEqual(payload["pollCalls"], ["/api/actions", "/api/state"])
        self.assertEqual(payload["startupLabel"], "启动灯")
        self.assertEqual(payload["motionStatus"], "醒着")

    def test_dashboard_js_refreshes_action_catalog_during_polling(self) -> None:
        source_path = ROOT / "dashboard.js"
        script = f"""
const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync({json.dumps(str(source_path))}, "utf8");
const pollCalls = [];
const nodes = {{}};
let actionCalls = 0;
let stateCalls = 0;

function createNode(id) {{
  return {{
    id,
    textContent: "",
    disabled: false,
    value: "",
    innerHTML: "",
    children: [],
    addEventListener: function () {{}},
    appendChild: function (child) {{
      this.children.push(child);
      if (typeof child.value !== "undefined") {{
        this.value = child.value;
      }}
    }},
  }};
}}

const context = {{
  console,
  Promise,
  JSON,
  setTimeout,
  clearTimeout,
}};

context.fetch = function (url) {{
  pollCalls.push(url);
  if (url === "/api/actions") {{
    actionCalls += 1;
    return Promise.resolve({{
      json: function () {{
        if (actionCalls === 1) {{
          return Promise.resolve({{
            busy: true,
            active_action: "startup",
            recordings: ["curious"],
            poll_ms: 400,
            actions: {{
              startup: {{ enabled: false, state: "running", label: "启动中" }},
              play: {{ enabled: false, state: "disabled", label: "Busy" }},
              stop: {{ enabled: false, state: "disabled", label: "Busy" }},
              shutdown_pose: {{ enabled: false, state: "disabled", label: "Busy" }},
              light_solid: {{ enabled: false, state: "disabled", label: "Busy" }},
              light_clear: {{ enabled: false, state: "disabled", label: "Busy" }},
            }},
          }});
        }}
        return Promise.resolve({{
          busy: false,
          active_action: null,
          recordings: ["curious"],
          poll_ms: 400,
          actions: {{
            startup: {{ enabled: true, state: "enabled", label: "启动灯" }},
            play: {{ enabled: true, state: "enabled", label: "播放动作" }},
            stop: {{ enabled: true, state: "enabled", label: "回到待机" }},
            shutdown_pose: {{ enabled: true, state: "enabled", label: "进入休息" }},
            light_solid: {{ enabled: true, state: "enabled", label: "暖黄灯光" }},
            light_clear: {{ enabled: true, state: "enabled", label: "关闭灯光" }},
          }},
        }});
      }},
    }});
  }}

  stateCalls += 1;
  return Promise.resolve({{
    json: function () {{
      if (stateCalls === 1) {{
        return Promise.resolve({{
          system: {{ status: "running", active_action: "startup", last_update_ms: 0, reachable_urls: [] }},
          motion: {{ status: "running", available_recordings: ["curious"] }},
          light: {{ status: "off" }},
          audio: {{ status: "ready" }},
          errors: [],
        }});
      }}
      return Promise.resolve({{
        system: {{ status: "ready", active_action: null, last_update_ms: 0, reachable_urls: [] }},
        motion: {{ status: "idle", available_recordings: ["curious"] }},
        light: {{ status: "off" }},
        audio: {{ status: "ready" }},
        errors: [],
      }});
    }},
  }});
}};

context.window = {{
  intervalMs: null,
  intervalFn: null,
  setInterval: function (fn, ms) {{
    this.intervalMs = ms;
    this.intervalFn = fn;
  }},
  addEventListener: function () {{}},
  fetch: null,
}};

context.document = {{
  getElementById: function (id) {{
    if (!nodes[id]) {{
      nodes[id] = createNode(id);
    }}
    return nodes[id];
  }},
  createElement: function () {{
    return createNode("option");
  }},
}};

context.window.fetch = context.fetch;
vm.createContext(context);
vm.runInContext(source, context);

Promise.resolve(context.DashboardApp.start(context.document, context.window, context.fetch, 400))
  .then(function () {{
    return new Promise(function (resolve) {{ setTimeout(resolve, 0); }});
  }})
  .then(function () {{
    context.window.intervalFn();
    return new Promise(function (resolve) {{ setTimeout(resolve, 0); }});
  }})
  .then(function () {{
    console.log(JSON.stringify({{
      intervalMs: context.window.intervalMs,
      pollCalls,
      startupLabel: nodes.startupButton.textContent,
      startupDisabled: nodes.startupButton.disabled,
      motionStatus: nodes.motionStatus.textContent,
    }}));
  }})
  .catch(function (error) {{
    console.error(error && error.stack ? error.stack : String(error));
    process.exit(1);
  }});
"""

        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout.strip())
        self.assertEqual(payload["intervalMs"], 400)
        self.assertEqual(
            payload["pollCalls"],
            ["/api/actions", "/api/state", "/api/actions", "/api/state"],
        )
        self.assertEqual(payload["startupLabel"], "启动灯")
        self.assertFalse(payload["startupDisabled"])
        self.assertEqual(payload["motionStatus"], "醒着")

    def test_dashboard_js_disables_controls_when_action_catalog_fails_and_resyncs_recordings_from_state(self) -> None:
        source_path = ROOT / "dashboard.js"
        script = f"""
const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync({json.dumps(str(source_path))}, "utf8");
const nodes = {{}};

function createNode(id) {{
  return {{
    id,
    textContent: "",
    disabled: false,
    value: "",
    innerHTML: "",
    children: [],
    addEventListener: function () {{}},
    appendChild: function (child) {{
      this.children.push(child);
      if (typeof child.value !== "undefined") {{
        this.value = child.value;
      }}
    }},
  }};
}}

const context = {{
  console,
  Promise,
  JSON,
  setTimeout,
  clearTimeout,
}};

context.fetch = function (url) {{
  if (url === "/api/actions") {{
    return Promise.reject(new Error("offline"));
  }}
  return Promise.resolve({{
    json: function () {{
      return Promise.resolve({{
        system: {{ status: "ready", active_action: null, last_update_ms: 0, reachable_urls: ["http://127.0.0.1:8765"], uptime_s: 3 }},
        motion: {{
          status: "idle",
          available_recordings: ["curious"],
          current_recording: null,
          last_completed_recording: null,
          home_recording: "home_safe",
          startup_recording: "wake_up",
          motors_connected: "unknown",
          calibration_state: "unknown",
          last_result: null
        }},
        light: {{ status: "off", color: null }},
        audio: {{ status: "ready", output_device: "Line", volume_percent: 64 }},
        errors: []
      }});
    }}
  }});
}};

context.window = {{
  intervalMs: null,
  setInterval: function (_fn, ms) {{ this.intervalMs = ms; }},
  addEventListener: function () {{}},
  fetch: null,
}};

context.document = {{
  getElementById: function (id) {{
    if (!nodes[id]) {{
      nodes[id] = createNode(id);
    }}
    return nodes[id];
  }},
  createElement: function () {{
    return createNode("option");
  }},
}};

context.window.fetch = context.fetch;
vm.createContext(context);
vm.runInContext(source, context);

Promise.resolve(context.DashboardApp.start(context.document, context.window, context.fetch, 400))
  .then(function () {{
    console.log(JSON.stringify({{
      startupDisabled: nodes.startupButton.disabled,
      playDisabled: nodes.playButton.disabled,
      recordings: nodes.recordingSelect.children.map(function (child) {{ return child.value; }}),
    }}));
  }})
  .catch(function (error) {{
    console.error(error && error.stack ? error.stack : String(error));
    process.exit(1);
  }});
"""

        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout.strip())
        self.assertTrue(payload["startupDisabled"])
        self.assertTrue(payload["playDisabled"])
        self.assertEqual(payload["recordings"], ["curious"])


if __name__ == "__main__":
    unittest.main()
