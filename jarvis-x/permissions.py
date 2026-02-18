"""Permission layer for sensitive actions."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PermissionManager:
    """Simple in-memory permissions for MVP."""

    _session_allow: set[str] = field(default_factory=set)

    def request(self, capability: str) -> bool:
        """For Phase 1, default to allow once with memoization hooks ready."""
        return capability in self._session_allow

    def allow_for_session(self, capability: str) -> None:
        self._session_allow.add(capability)
