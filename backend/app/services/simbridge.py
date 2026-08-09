"""Bridge from the API to the simulation/ package (Phase 8).

Mirrors mlbridge's layout discipline: simulation/ lives at the repo root beside
backend/ (and at /app/simulation inside the API container via find_repo_root's
marker walk — no hardcoded parents[N]). The engine is pure stdlib; the API stays
torch-free; every payload this module produces already carries the simulation
label + assumptions verbatim from the engine.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db import models

_ENGINE = None


def find_simulation_root(start: Path | None = None) -> Path:
    """Locate the repo root by the simulation/ marker — NOT via mlbridge's ml/configs
    marker, because the API container ships simulation/ but not ml/ (ml_configs only).

    Layouts: local checkout ``<repo>/backend/app/...`` and API container ``/app/app/...``
    (Dockerfile COPYs simulation/ → /app/simulation). Refuses to guess, like mlbridge.
    """
    start_dir = Path(start).resolve() if start else Path(__file__).resolve().parent
    for candidate in [start_dir, *start_dir.parents]:
        if (candidate / "simulation" / "spray_simulator.py").is_file():
            return candidate
    raise RuntimeError(f"simulation/ package not found above {start_dir} (no spray_simulator marker)")


def _engine():
    global _ENGINE
    if _ENGINE is None:
        root = find_simulation_root()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        import simulation
        from simulation import drone_simulator, spray_simulator

        _ENGINE = (spray_simulator, drone_simulator, simulation.__version__)
    return _ENGINE


def run_spray_plan(db: Session, field: models.Field, inputs: dict[str, Any]) -> models.SimulationRun:
    """Validate with the engine, run it, persist params + labelled result verbatim."""
    spray_simulator, drone_simulator, _version = _engine()
    boundary = field.boundary_geojson
    treatments = [t["coordinates"][0] for t in inputs["treatment_polygons"]]
    params = spray_simulator.SprayParams(
        boundary_lonlat=boundary["coordinates"][0],
        treatments_lonlat=treatments,
        spray_width_m=inputs["spray_width_m"],
        speed_mps=inputs["speed_mps"],
        declared_rate_l_per_ha=inputs["declared_rate_l_per_ha"],
        turn_overhead_s=inputs["turn_overhead_s"],
    )
    result = spray_simulator.run(params, swath_cap=inputs.get("swath_cap", spray_simulator.DEFAULT_SWATH_CAP))

    # Prove the provider seam end-to-end without hardware: the simulated drone
    # receives the mission and returns an intent receipt (never flown anything).
    drone = drone_simulator.SimulatedDroneProvider()
    mission_id = drone.upload_mission(
        {"kind": "SPRAY_PLAN", "field_id": field.id, "swath_count": result["swath_count"], "route_length_m": result["route_length_m"]}
    )

    params_json = {
        "field_id": field.id,
        "boundary_geojson": boundary,
        "treatment_polygons": inputs["treatment_polygons"],
        "spray_width_m": inputs["spray_width_m"],
        "speed_mps": inputs["speed_mps"],
        "declared_rate_l_per_ha": inputs["declared_rate_l_per_ha"],
        "turn_overhead_s": inputs["turn_overhead_s"],
    }
    result_json = {
        **result,
        "inputs": params_json,
        "provider_receipt": drone.receipt(mission_id),
        "engine": {"package": "simulation", "version": _engine_version()},
        "honesty_notice": "SIMULATION: area × declared-rate arithmetic only — no product, chemical or dosage guidance exists in this output",
    }
    run_row = models.SimulationRun(
        run_kind="SPRAY_PLAN",
        field_id=field.id,
        mission_id=mission_id,
        params_json=params_json,
        result_json=result_json,
    )
    db.add(run_row)
    db.flush()
    return run_row


def _engine_version() -> str:
    return str(_engine()[2])


def simulation_payload(run_row: models.SimulationRun, *, summary: bool = False) -> dict[str, Any]:
    result = run_row.result_json
    base = {
        "simulation_id": run_row.id,
        "run_kind": run_row.run_kind,
        "field_id": run_row.field_id,
        "mission_id": run_row.mission_id,
        "created_at": run_row.created_at.isoformat() if run_row.created_at else None,
        "simulation_label": result.get("simulation_label"),
        "saved_inputs_echo": summary,
    }
    if summary:
        base["key_results"] = {
            "treated_fraction": result["treated_fraction"],
            "savings_pct": result["savings_pct"],
            "savings_volume_l": result["savings_volume_l"],
            "swath_count": result["swath_count"],
        }
    else:
        base["params"] = run_row.params_json
        base["results"] = result
    return base
