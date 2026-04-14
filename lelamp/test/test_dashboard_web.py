import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "dashboard" / "web"


class DashboardWebTests(unittest.TestCase):
    def test_index_contains_primary_control_regions(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="connectionStatus"', html)
        self.assertIn('id="systemStatus"', html)
        self.assertIn('id="startupButton"', html)
        self.assertIn('id="shutdownPoseButton"', html)
        self.assertIn('id="diagnosticsPanel"', html)
        self.assertIn('id="recordingList"', html)

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
            startup: {{ enabled: true }},
            play: {{ enabled: true }},
            stop: {{ enabled: true }},
            shutdown_pose: {{ enabled: true }},
            light_solid: {{ enabled: true }},
            light_clear: {{ enabled: true }},
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


if __name__ == "__main__":
    unittest.main()
