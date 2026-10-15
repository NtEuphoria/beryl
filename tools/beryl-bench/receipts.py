#!/usr/bin/env python3
"""Write evaluator-v1 receipts. Does not time anything."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

COSTS = (
    "setup", "capture", "compute", "maintenance",
    "invalidation", "conversion", "cleanup", "cold_refresh",
)
RESOURCES = (
    "peak_bytes", "retained_bytes", "allocations",
    "text_bytes", "build_ns", "edit_check_ns",
)
IDENTITIES = (
    "baseline", "compiler", "toolchain",
    "environment", "workload", "semantic_contract",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def write_bytes(root: Path, name: str, data: bytes) -> dict:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": name.replace("\\", "/"), "sha256": digest(data)}


def write_json(root: Path, name: str, value) -> dict:
    return write_bytes(root, name, canonical(value) + b"\n")


def write_text(root: Path, name: str, text: str) -> dict:
    return write_bytes(root, name, text.encode("utf-8"))


def measurement(
    *,
    measurement_id: str,
    unit_id: str,
    session_id: str,
    started: int,
    ended: int,
    fingerprints: dict,
    paid: dict,
    resources: dict,
    semantic: dict,
) -> dict:
    total = sum(paid[key] for key in COSTS)
    return {
        "schema_version": 1,
        "kind": "beryl.performance.measurement",
        "measurement_id": measurement_id,
        "unit_id": unit_id,
        "session_id": session_id,
        "status": "complete",
        "started_utc_ns": started,
        "ended_utc_ns": ended,
        "fingerprints": fingerprints,
        "paid_ns": paid,
        "total_paid_ns": total,
        "resources": resources,
        "semantic": semantic,
    }


def independence(*, unit_id: str, measurement_ids: list, evidence: dict) -> dict:
    return {
        "schema_version": 1,
        "kind": "beryl.performance.independence",
        "status": "verified",
        "unit_id": unit_id,
        "method": "separate_owned_sessions",
        "measurement_ids": measurement_ids,
        "evidence": evidence,
    }


def pilot(*, experiment_id: str, population: str, fingerprints: dict,
          budgets: dict, blocks: list) -> dict:
    return {
        "schema_version": 1,
        "kind": "beryl.performance.pilot",
        "experiment_id": experiment_id,
        "evidence_kind": "collector_measurements",
        "resource_policy": "resource_adequate_exact",
        "metric": "median_paired_total_paid_ns",
        "population": {
            "sampling": "independent_identically_distributed",
            "description": population,
        },
        "fingerprints": fingerprints,
        "budgets": budgets,
        "blocks": blocks,
    }


def selection(*, candidate_sha256: str, selected_utc_ns: int, evidence: dict) -> dict:
    return {
        "schema_version": 1,
        "kind": "beryl.performance.selection",
        "status": "frozen",
        "candidate_sha256": candidate_sha256,
        "selected_utc_ns": selected_utc_ns,
        "prior_workload_sha256": [],
        "evidence": evidence,
    }


def evaluation(*, freeze: dict, candidate: dict, selection_ref: dict,
               blocks: list) -> dict:
    return {
        "schema_version": 1,
        "kind": "beryl.performance.evaluation",
        "freeze": freeze,
        "candidate": candidate,
        "selection": selection_ref,
        "role": "held_out",
        "blocks": blocks,
    }
