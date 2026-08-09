"""Simulated drone provider (Phase 8) — the DroneProvider seam from docs/02 §8.

Records mission intent ONLY: calling upload_mission proves the API → provider
contract works end to end without any hardware, and the receipt says exactly
that. A real vendor adapter implements the same Protocol later; nothing above
this layer changes.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol


class DroneProvider(Protocol):
    def upload_mission(self, mission: dict[str, Any]) -> str: ...
    def get_telemetry(self, mission_id: str) -> dict[str, Any]: ...


class SimulatedDroneProvider:
    name = "simulated-drone-v1"

    def __init__(self) -> None:
        self._missions: dict[str, dict[str, Any]] = {}

    def upload_mission(self, mission: dict[str, Any]) -> str:
        mission_id = f"SIM-{uuid.uuid4().hex[:8]}"
        self._missions[mission_id] = {"mission": mission, "status": "ACCEPTED-SIMULATED"}
        return mission_id

    def get_telemetry(self, mission_id: str) -> dict[str, Any]:
        record = self._missions.get(mission_id)
        if record is None:
            raise KeyError(f"unknown simulated mission {mission_id}")
        return {
            "mission_id": mission_id,
            "status": record["status"],
            "note": "simulated provider — no aircraft exists; this records intent only",
        }

    def receipt(self, mission_id: str) -> dict[str, Any]:
        telemetry = self.get_telemetry(mission_id)
        return {
            "provider": self.name,
            "mission_id": mission_id,
            "status": telemetry["status"],
            "note": telemetry["note"],
        }
