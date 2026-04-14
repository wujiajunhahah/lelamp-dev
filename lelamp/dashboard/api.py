"""FastAPI app for the local LeLamp dashboard."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from lelamp.dashboard.actions import (
    DashboardActionExecutor,
    build_light_actions,
    build_motion_actions,
)
from lelamp.dashboard.runtime_bridge import DashboardRuntimeBridge
from lelamp.dashboard.samplers import DashboardSamplerLoop
from lelamp.dashboard.state_store import DashboardStateStore
from lelamp.runtime_config import load_runtime_settings


WEB_DIR = Path(__file__).resolve().parent / "web"


def _receipt_response(receipt: Any) -> JSONResponse:
    status_code = 202
    if not receipt.ok and getattr(receipt, "error", None) == "busy":
        status_code = 409
    elif not receipt.ok:
        status_code = 500
    return JSONResponse(status_code=status_code, content=dict(vars(receipt)))


def create_app(
    *,
    settings=None,
    store=None,
    bridge=None,
    executor=None,
    enable_background: bool = True,
) -> FastAPI:
    settings = settings or load_runtime_settings()
    store = store or DashboardStateStore()
    bridge = bridge or DashboardRuntimeBridge(settings)
    executor = executor or DashboardActionExecutor(store)
    sampler = (
        DashboardSamplerLoop(store, settings, bridge, executor)
        if enable_background
        else None
    )

    motion_actions = build_motion_actions(executor, bridge)
    light_actions = build_light_actions(executor, bridge)

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        if sampler is not None:
            sampler.start()
        try:
            yield
        finally:
            if sampler is not None:
                sampler.stop()

    app = FastAPI(title="LeLamp Dashboard", lifespan=_lifespan)
    app.mount("/static", StaticFiles(directory=WEB_DIR, check_dir=False), name="static")

    @app.get("/")
    def index() -> FileResponse:
        index_path = WEB_DIR / "index.html"
        if not index_path.is_file():
            raise HTTPException(status_code=404, detail="Dashboard UI not built yet.")
        return FileResponse(index_path)

    @app.get("/api/state")
    def get_state() -> dict[str, object]:
        return store.snapshot()

    @app.get("/api/actions")
    def get_actions() -> dict[str, object]:
        busy = executor.is_busy()
        return {
            "busy": busy,
            "active_action": executor.current_action(),
            "recordings": bridge.list_recordings(),
            "poll_ms": settings.dashboard_poll_ms,
            "actions": {
                "startup": {"enabled": not busy},
                "play": {"enabled": not busy},
                "stop": {"enabled": not busy},
                "shutdown_pose": {"enabled": not busy},
                "light_solid": {"enabled": not busy},
                "light_clear": {"enabled": not busy},
            },
        }

    @app.post("/api/actions/startup")
    def post_startup() -> JSONResponse:
        return _receipt_response(motion_actions["startup"]())

    @app.post("/api/actions/play")
    def post_play(payload: dict[str, str]) -> JSONResponse:
        name = payload.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="Missing recording name.")
        return _receipt_response(motion_actions["play"](name))

    @app.post("/api/actions/shutdown_pose")
    def post_shutdown_pose() -> JSONResponse:
        return _receipt_response(motion_actions["shutdown_pose"]())

    @app.post("/api/actions/stop")
    def post_stop() -> JSONResponse:
        return _receipt_response(motion_actions["stop"]())

    @app.post("/api/lights/solid")
    def post_solid(payload: dict[str, int]) -> JSONResponse:
        required = ("red", "green", "blue")
        if any(channel not in payload for channel in required):
            raise HTTPException(status_code=400, detail="Missing RGB channel value.")
        return _receipt_response(
            light_actions["solid"](payload["red"], payload["green"], payload["blue"])
        )

    @app.post("/api/lights/clear")
    def post_clear() -> JSONResponse:
        return _receipt_response(light_actions["clear"]())

    return app


if __name__ == "__main__":
    runtime_settings = load_runtime_settings()
    uvicorn.run(
        "lelamp.dashboard.api:create_app",
        factory=True,
        host=runtime_settings.dashboard_host,
        port=runtime_settings.dashboard_port,
    )
