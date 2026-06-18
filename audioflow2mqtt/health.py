"""Pure device-health model: consecutive failures -> online/offline.

Immutable. `succeeded()`/`failed()` return a new DeviceHealth; the orchestrator
compares the `online` flag before/after to publish status only on a transition.
Replaces the monolith's ad-hoc retry_count.
"""
from __future__ import annotations

from dataclasses import dataclass

OFFLINE_THRESHOLD = 3


@dataclass(frozen=True)
class DeviceHealth:
    failures: int = 0
    online: bool = True

    def failed(self, threshold: int = OFFLINE_THRESHOLD) -> "DeviceHealth":
        failures = self.failures + 1
        return DeviceHealth(failures=failures, online=failures < threshold)

    def succeeded(self) -> "DeviceHealth":
        return DeviceHealth(failures=0, online=True)
