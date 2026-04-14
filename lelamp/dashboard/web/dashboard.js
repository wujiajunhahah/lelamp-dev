var DashboardApp = (function () {
  var ACTION_META = {
    startupButton: { actionKey: "startup", baseClass: "action-button action-button--primary", label: "Startup" },
    playButton: { actionKey: "play", baseClass: "action-button", label: "Play Motion" },
    stopButton: { actionKey: "stop", baseClass: "action-button", label: "Return Home" },
    shutdownPoseButton: { actionKey: "shutdown_pose", baseClass: "action-button action-button--warn", label: "Shutdown Pose" },
    lightAmberButton: { actionKey: "light_solid", baseClass: "action-button action-button--amber", label: "Warm Amber" },
    lightClearButton: { actionKey: "light_clear", baseClass: "action-button", label: "Light Off" },
  };
  var runtimeMeta = {
    pollMs: 400,
    dashboardHost: "0.0.0.0",
    dashboardPort: 8765,
  };

  function byId(documentRef, id) {
    return documentRef.getElementById(id);
  }

  function text(node, value) {
    if (node) {
      node.textContent = value == null ? "" : String(value);
    }
  }

  function setClassName(node, className) {
    if (node) {
      node.className = className;
    }
  }

  function statusTone(status) {
    if (status === "ready" || status === "solid" || status === "muted") {
      return "ready";
    }
    if (status === "running" || status === "transition") {
      return "running";
    }
    if (status === "warning") {
      return "warn";
    }
    if (status === "error") {
      return "error";
    }
    if (status === "live") {
      return "live";
    }
    if (status === "offline") {
      return "offline";
    }
    return "unknown";
  }

  function formatRgb(color) {
    if (!color) {
      return "--";
    }
    return [color.red, color.green, color.blue].join(", ");
  }

  function formatVolume(audio) {
    if (!audio || audio.volume_percent == null) {
      return audio && audio.output_device ? audio.output_device : "--";
    }
    return String(audio.volume_percent) + "%";
  }

  function formatMs(value) {
    return String(value || 0) + " ms";
  }

  function formatSeconds(value) {
    return String(value || 0) + " s";
  }

  function renderTokens(node, items, emptyLabel) {
    if (!node) {
      return;
    }

    if (!items || !items.length) {
      node.innerHTML = '<span class="token-list__item token-list__item--empty">' + emptyLabel + "</span>";
      return;
    }

    node.innerHTML = items
      .map(function (item) {
        return '<span class="token-list__item">' + String(item) + "</span>";
      })
      .join("");
  }

  function renderErrors(node, errors) {
    if (!node) {
      return;
    }

    if (!errors || !errors.length) {
      node.innerHTML = '<div class="error-feed__item"><div class="error-feed__message">No active errors.</div></div>';
      return;
    }

    node.innerHTML = errors
      .map(function (error) {
        var severity = error.severity || "warning";
        var status = error.active ? "active" : "resolved";
        return (
          '<div class="error-feed__item error-feed__item--' + severity + '">' +
          '<div class="error-feed__meta"><span>' + severity + "</span><span>" + status + "</span></div>" +
          '<div class="error-feed__message">' + String(error.message || error.code || "Unknown error") + "</div>" +
          "</div>"
        );
      })
      .join("");
  }

  function buttonClass(baseClass, state) {
    if (state === "running") {
      return baseClass + " action-button--running";
    }
    if (state === "error") {
      return baseClass + " action-button--error";
    }
    if (state === "disabled") {
      return baseClass + " action-button--disabled";
    }
    return baseClass;
  }

  function defaultActionPayload(disableAll) {
    var payload = {
      busy: disableAll,
      actions: {},
      recordings: [],
      poll_ms: runtimeMeta.pollMs,
      config: {
        dashboard_host: runtimeMeta.dashboardHost,
        dashboard_port: runtimeMeta.dashboardPort,
        poll_ms: runtimeMeta.pollMs,
      },
    };

    Object.keys(ACTION_META).forEach(function (id) {
      var meta = ACTION_META[id];
      payload.actions[meta.actionKey] = {
        enabled: !disableAll,
        state: disableAll ? "disabled" : "enabled",
        label: disableAll ? "Unavailable" : meta.label,
      };
    });

    return payload;
  }

  function applyActionAvailability(documentRef, payload) {
    var actions = payload && payload.actions ? payload.actions : defaultActionPayload(true).actions;

    Object.keys(ACTION_META).forEach(function (id) {
      var node = byId(documentRef, id);
      var meta = ACTION_META[id];
      var config = actions[meta.actionKey] || {
        enabled: false,
        state: "disabled",
        label: "Unavailable",
      };
      if (node) {
        node.disabled = config.enabled === false;
        node.textContent = config.label || meta.label;
        node.className = buttonClass(meta.baseClass, config.state || "enabled");
      }
    });
  }

  function populateRecordings(documentRef, recordings) {
    var select = byId(documentRef, "recordingSelect");
    var currentValue;
    if (!select) {
      return;
    }

    currentValue = select.value;
    select.innerHTML = "";
    if (select.children && typeof select.children.length === "number") {
      select.children.length = 0;
    }
    if (!recordings || !recordings.length) {
      select.disabled = true;
      select.value = "";
      return;
    }

    select.disabled = false;
    recordings.forEach(function (recording, index) {
      var option = documentRef.createElement("option");
      option.value = recording;
      option.textContent = recording;
      if (currentValue && currentValue === recording) {
        select.value = recording;
      } else if (!select.value && index === 0) {
        select.value = recording;
      }
      if (select.appendChild) {
        select.appendChild(option);
      }
    });
  }

  function renderHardwareNotes(documentRef, motion, light, audio) {
    renderTokens(byId(documentRef, "hardwareNotes"), [
      "motors=" + String(motion.motors_connected == null ? "unknown" : motion.motors_connected),
      "calibration=" + String(motion.calibration_state || "unknown"),
      "audio=" + String(audio.output_device || "unknown"),
      "light=" + String(light.status || "unknown"),
    ], "No hardware notes yet.");
  }

  function renderConnectivityHints(documentRef, reachableUrls) {
    var hints = [];
    if (reachableUrls && reachableUrls.length) {
      hints.push("Pi screen: http://127.0.0.1:8765");
      hints = hints.concat(reachableUrls.slice(0, 2).map(function (url) {
        return "Nearby device: " + url;
      }));
    }
    renderTokens(byId(documentRef, "connectivityHints"), hints, "No connectivity hints yet.");
  }

  function renderConfigSnippets(documentRef, motion) {
    renderTokens(byId(documentRef, "configSnippets"), [
      "LELAMP_DASHBOARD_HOST=" + runtimeMeta.dashboardHost,
      "LELAMP_DASHBOARD_PORT=" + String(runtimeMeta.dashboardPort),
      "LELAMP_DASHBOARD_POLL_MS=" + String(runtimeMeta.pollMs),
      "LELAMP_HOME_RECORDING=" + String(motion.home_recording || "--"),
      "LELAMP_STARTUP_RECORDING=" + String(motion.startup_recording || "--"),
    ], "No config snippets yet.");
  }

  function renderState(documentRef, state) {
    var system = state.system || {};
    var motion = state.motion || {};
    var light = state.light || {};
    var audio = state.audio || {};
    var reachable = system.reachable_urls || [];
    var connection = reachable.length ? "live" : "offline";

    text(byId(documentRef, "connectionStatus"), connection);
    text(byId(documentRef, "systemStatus"), system.status || "unknown");
    text(byId(documentRef, "activeAction"), system.active_action || "idle");
    text(byId(documentRef, "lastUpdateTopbar"), formatMs(system.last_update_ms));
    text(byId(documentRef, "lastUpdate"), formatMs(system.last_update_ms));
    text(byId(documentRef, "uptimeSeconds"), formatSeconds(system.uptime_s));

    text(byId(documentRef, "motionStatus"), motion.status || "unknown");
    text(byId(documentRef, "motionResult"), motion.last_result || "No motion result yet.");
    text(byId(documentRef, "currentRecording"), motion.current_recording || "--");
    text(byId(documentRef, "lastCompletedRecording"), motion.last_completed_recording || "--");
    text(byId(documentRef, "homeRecording"), motion.home_recording || "--");
    text(byId(documentRef, "startupRecording"), motion.startup_recording || "--");
    text(byId(documentRef, "motorConnectivity"), motion.motors_connected == null ? "unknown" : motion.motors_connected);
    text(byId(documentRef, "calibrationState"), motion.calibration_state || "unknown");

    text(byId(documentRef, "lightStatus"), light.status || "unknown");
    text(byId(documentRef, "lightColor"), formatRgb(light.color));

    text(byId(documentRef, "audioStatus"), audio.status || "unknown");
    text(byId(documentRef, "audioVolume"), formatVolume(audio));

    setClassName(byId(documentRef, "connectionStatus"), "status-pill status-pill--" + statusTone(connection));
    setClassName(byId(documentRef, "systemStatus"), "status-pill status-pill--" + statusTone(system.status || "unknown"));

    populateRecordings(documentRef, motion.available_recordings || []);
    renderTokens(byId(documentRef, "reachableUrls"), reachable, "No reachable URLs reported yet.");
    renderTokens(byId(documentRef, "recordingList"), motion.available_recordings || [], "No recordings discovered.");
    renderHardwareNotes(documentRef, motion, light, audio);
    renderConnectivityHints(documentRef, reachable);
    renderConfigSnippets(documentRef, motion);
    renderErrors(byId(documentRef, "errorFeed"), state.errors || []);
  }

  function pollState(fetchRef, onState) {
    return fetchRef("/api/state")
      .then(function (response) {
        return response.json();
      })
      .then(function (state) {
        onState(state);
        return state;
      })
      .catch(function () {
        var fallback = {
          system: { status: "unknown", active_action: null, last_update_ms: 0, reachable_urls: [], uptime_s: 0 },
          motion: { status: "unknown", available_recordings: [] },
          light: { status: "unknown", color: null },
          audio: { status: "unknown", output_device: null, volume_percent: null },
          errors: [{ code: "ui.poll_failed", message: "State polling failed.", severity: "warning", active: true }],
        };
        onState(fallback);
        return fallback;
      });
  }

  function loadActions(documentRef, fetchRef) {
    return fetchRef("/api/actions")
      .then(function (response) {
        return response.json();
      })
      .then(function (payload) {
        runtimeMeta.pollMs = payload.poll_ms || runtimeMeta.pollMs;
        if (payload.config) {
          runtimeMeta.dashboardHost = payload.config.dashboard_host || runtimeMeta.dashboardHost;
          runtimeMeta.dashboardPort = payload.config.dashboard_port || runtimeMeta.dashboardPort;
        }
        applyActionAvailability(documentRef, payload);
        populateRecordings(documentRef, payload.recordings || []);
        return payload;
      })
      .catch(function () {
        var fallback = defaultActionPayload(true);
        applyActionAvailability(documentRef, fallback);
        return fallback;
      });
  }

  function postJson(fetchRef, url, payload) {
    return fetchRef(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload ? JSON.stringify(payload) : "{}",
    })
      .then(function (response) {
        if (response && response.json) {
          return response.json();
        }
        return {};
      })
      .catch(function () {
        return {};
      });
  }

  function refresh(documentRef, fetchRef) {
    return loadActions(documentRef, fetchRef).then(function () {
      return pollState(fetchRef, function (state) {
        renderState(documentRef, state);
      });
    });
  }

  function wireActions(documentRef, fetchRef) {
    var recordingSelect = byId(documentRef, "recordingSelect");

    function bind(id, handler) {
      var node = byId(documentRef, id);
      if (node && node.addEventListener) {
        node.addEventListener("click", handler);
      }
    }

    bind("startupButton", function () {
      postJson(fetchRef, "/api/actions/startup").then(function () {
        return refresh(documentRef, fetchRef);
      });
    });
    bind("playButton", function () {
      postJson(fetchRef, "/api/actions/play", {
        name: recordingSelect ? recordingSelect.value : "",
      }).then(function () {
        return refresh(documentRef, fetchRef);
      });
    });
    bind("stopButton", function () {
      postJson(fetchRef, "/api/actions/stop").then(function () {
        return refresh(documentRef, fetchRef);
      });
    });
    bind("shutdownPoseButton", function () {
      postJson(fetchRef, "/api/actions/shutdown_pose").then(function () {
        return refresh(documentRef, fetchRef);
      });
    });
    bind("lightAmberButton", function () {
      postJson(fetchRef, "/api/lights/solid", { red: 255, green: 178, blue: 91 }).then(function () {
        return refresh(documentRef, fetchRef);
      });
    });
    bind("lightClearButton", function () {
      postJson(fetchRef, "/api/lights/clear").then(function () {
        return refresh(documentRef, fetchRef);
      });
    });
  }

  function start(documentRef, windowRef, fetchRef, pollMs) {
    wireActions(documentRef, fetchRef);
    return loadActions(documentRef, fetchRef).then(function (payload) {
      var effectivePollMs = payload.poll_ms || pollMs;
      return pollState(fetchRef, function (state) {
        renderState(documentRef, state);
      }).then(function () {
        windowRef.setInterval(function () {
          pollState(fetchRef, function (state) {
            renderState(documentRef, state);
          });
        }, effectivePollMs);
        return payload;
      });
    });
  }

  return {
    applyActionAvailability: applyActionAvailability,
    loadActions: loadActions,
    pollState: pollState,
    renderState: renderState,
    start: start,
  };
}());

window.addEventListener("DOMContentLoaded", function () {
  DashboardApp.start(document, window, window.fetch.bind(window), 400);
});
