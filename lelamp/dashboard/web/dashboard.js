var DashboardApp = (function () {
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

  function disableButtons(documentRef, isBusy) {
    [
      "startupButton",
      "playButton",
      "stopButton",
      "shutdownPoseButton",
      "lightAmberButton",
      "lightClearButton"
    ].forEach(function (id) {
      var node = byId(documentRef, id);
      if (node) {
        node.disabled = Boolean(isBusy);
      }
    });
  }

  function applyActionAvailability(documentRef, payload) {
    var busy = Boolean(payload && payload.busy);
    var actions = payload && payload.actions ? payload.actions : {};
    var mapping = {
      startupButton: "startup",
      playButton: "play",
      stopButton: "stop",
      shutdownPoseButton: "shutdown_pose",
      lightAmberButton: "light_solid",
      lightClearButton: "light_clear"
    };

    Object.keys(mapping).forEach(function (id) {
      var node = byId(documentRef, id);
      var config = actions[mapping[id]];
      if (node) {
        node.disabled = busy || (config && config.enabled === false);
      }
    });
  }

  function populateRecordings(documentRef, recordings) {
    var select = byId(documentRef, "recordingSelect");
    if (!select) {
      return;
    }

    select.innerHTML = "";
    if (!recordings || !recordings.length) {
      return;
    }

    recordings.forEach(function (recording, index) {
      var option = documentRef.createElement("option");
      option.value = recording;
      option.textContent = recording;
      if (index === 0) {
        select.value = recording;
      }
      if (select.appendChild) {
        select.appendChild(option);
      }
    });
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

    renderTokens(byId(documentRef, "reachableUrls"), reachable, "No reachable URLs reported yet.");
    renderTokens(byId(documentRef, "recordingList"), motion.available_recordings || [], "No recordings discovered.");
    renderErrors(byId(documentRef, "errorFeed"), state.errors || []);
    disableButtons(documentRef, system.status === "running");
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
        applyActionAvailability(documentRef, payload);
        populateRecordings(documentRef, payload.recordings || []);
        return payload;
      })
      .catch(function () {
        var fallback = {
          busy: false,
          recordings: [],
          poll_ms: 400,
          actions: {},
        };
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
