"""Prime's verdict and the agent jobs list --
everything the live JSON API and the `push` command render, as data."""

from __future__ import annotations

from sinnix_lib.ledger import utc_ts

from .hub import hub_get


def build_glance() -> dict:
    """Prime's verdict, as data.

    Deliberately small and deliberately quiet-by-default. `attention` is empty
    when nothing needs a human, because the phone renders absence as the
    resting state — a strip that always has content is a strip nobody reads.
    """
    snapshot = hub_get("/v1/snapshot") or {}
    attention: list[dict] = []
    tiles: list[dict] = []

    units = snapshot.get("units")
    failed = (
        [
            u
            for u in units
            if isinstance(u, dict) and str(u.get("state", "")).startswith("fail")
        ]
        if isinstance(units, list)
        else []
    )
    for u in failed[:5]:
        attention.append(
            {
                "kind": "unit_failed",
                "text": f"{u.get('unit')} is {u.get('state')}",
                "target": u.get("unit"),
            }
        )

    gateway = snapshot.get("agent_gateway")
    jobs = gateway.get("jobs") if isinstance(gateway, dict) else None
    if isinstance(jobs, list):
        waiting = [
            j
            for j in jobs
            if isinstance(j, dict) and j.get("state") == "waiting_on_operator"
        ]
        for j in waiting[:3]:
            attention.append(
                {
                    "kind": "agent_question",
                    "text": j.get("question") or f"{j.get('job_id')} is waiting",
                    "job_id": j.get("job_id"),
                }
            )
        tiles.append({"label": "agent jobs", "value": str(len(jobs))})

    pressure = snapshot.get("pressure")
    if isinstance(pressure, dict):
        for key in ("memory", "cpu", "io"):
            value = pressure.get(key)
            if value is not None:
                tiles.append({"label": key, "value": str(value)})

    verdict = "all quiet" if not attention else f"{len(attention)} want you"
    return {
        "schema": "sinnix.phone.glance/1",
        "generated_at": utc_ts(),
        "verdict": verdict,
        "attention": attention,
        "tiles": tiles,
        "hub_seen": bool(snapshot),
    }


def build_jobs() -> dict:
    snapshot = hub_get("/v1/snapshot") or {}
    gateway = snapshot.get("agent_gateway")
    jobs = gateway.get("jobs") if isinstance(gateway, dict) else []
    rows = []
    for j in jobs if isinstance(jobs, list) else []:
        if not isinstance(j, dict):
            continue
        rows.append(
            {
                "id": j.get("job_id"),
                "summary": j.get("work_item") or j.get("summary") or j.get("job_id"),
                "backend": j.get("backend"),
                "model": j.get("model"),
                "state": j.get("state"),
                "question": j.get("question"),
                "elapsed": j.get("elapsed"),
            }
        )
    return {"jobs": rows, "generated_at": utc_ts()}
