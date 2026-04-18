"""Runtime-safe integration seam for H1 memory.

This module is the only place runtime hot paths should touch the memory
library directly.  It turns the file-backed writer/session APIs into a
small no-throw surface so voice-agent bootstrap can opt in without
risking Pi uptime.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from .selfcheck import run_selfcheck
from .session import SessionHandle, start_agent_session
from .writer import MemoryWriter

_logger = logging.getLogger(__name__)

_DISABLE_ENV = "LELAMP_MEMORY_DISABLE"
_TRUE_VALUES = {"1", "true", "yes", "on"}


def _runtime_disabled() -> bool:
    value = os.environ.get(_DISABLE_ENV, "").strip().lower()
    return value in _TRUE_VALUES


@dataclass
class AgentMemoryRuntime:
    enabled: bool = False
    writer: Optional[MemoryWriter] = None
    session_handle: Optional[SessionHandle] = None
    _closed: bool = field(default=False, init=False, repr=False)

    def set_motor_bus_enabled(self, enabled: Optional[bool]) -> None:
        if not self.enabled or self._closed or self.session_handle is None:
            return
        try:
            self.session_handle.set_motor_bus_enabled(enabled)
        except Exception:
            _logger.exception(
                "memory runtime: failed to patch motor_bus_enabled=%r",
                enabled,
            )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if not self.enabled or self.session_handle is None:
            return
        try:
            self.session_handle.close()
        except Exception:
            _logger.exception("memory runtime: failed to close session")


def bootstrap_agent_runtime(settings, *, user_id: Optional[str] = None) -> AgentMemoryRuntime:
    if _runtime_disabled():
        return AgentMemoryRuntime(enabled=False)

    try:
        writer = MemoryWriter(user_id=user_id)
        run_selfcheck(writer)
        providers = []
        model_provider = getattr(settings, "model_provider", None)
        if isinstance(model_provider, str) and model_provider:
            providers.append(model_provider)
        session_handle = start_agent_session(
            writer,
            model_providers=providers,
        )
    except Exception:
        _logger.exception("memory runtime: bootstrap failed, degrading to no-op")
        return AgentMemoryRuntime(enabled=False)

    return AgentMemoryRuntime(
        enabled=True,
        writer=writer,
        session_handle=session_handle,
    )
