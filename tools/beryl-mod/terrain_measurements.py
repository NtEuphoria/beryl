"""Bounded exploratory target collection through the existing scenario bridge."""
from pathlib import Path
import re
import terrain_scenarios as terrain

SCOPE_NAME = "terrain_construct_release"
SCOPE = "Cached-height relief command construction and release with command-count observation; excludes sample preparation, sampling, Canvas publication, rendering, other layers and MESH integration"


def registry():
    return {"name": "measure.terrain.construction", "implementation": "implemented",
            "runtime_status": "requires explicit frozen exploratory schedule and separate complete semantic receipt",
            "case_ids": list(terrain.CASES), "count_parameter": "use typed --measurement-plan; 30..120 balanced pairs, 1..32 operations",
            "evidence_scope": SCOPE, "adoption_eligible": False}


def validate_plan(api, plan):
    fields = {"schema_version", "kind", "experiment_id", "phase", "role", "created_utc_ns", "scope_name", "operations", "case_ids", "pair_count", "runs"}
    if type(plan) is not dict or set(plan) != fields or type(plan["schema_version"]) is not int or plan["schema_version"] != 1 or plan["kind"] != "beryl.performance.schedule":
        raise api.Failure("Unsupported measurement schedule schema")
    if plan["phase"] != "exploratory" or plan["role"] != "exploratory" or plan["scope_name"] != SCOPE_NAME:
        raise api.Failure("This engine adapter admits exploratory terrain_construct_release schedules only")
    if type(plan["experiment_id"]) is not str or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", plan["experiment_id"]):
        raise api.Failure("Invalid experiment identity")
    if type(plan["created_utc_ns"]) is not int or plan["created_utc_ns"] <= 0:
        raise api.Failure("Missing schedule creation timestamp")
    selected, count, operations = plan["case_ids"], plan["pair_count"], plan["operations"]
    if type(selected) is not list or not selected or any(type(name) is not str or name not in terrain.CASES for name in selected) or len(set(selected)) != len(selected):
        raise api.Failure("Invalid terrain measurement case selection")
    if type(count) is not int or not 30 <= count <= 120 or count % (2 * len(selected)):
        raise api.Failure("Measurement pairs must be 30..120, balanced separately for every fixture")
    if type(operations) is not int or not 1 <= operations <= 32:
        raise api.Failure("Measurement operations must be an integer from 1 to 32")
    expected = []
    for pair in range(count):
        first = "a" if (pair // len(selected)) % 2 == 0 else "b"
        for side in (first, "b" if first == "a" else "a"):
            expected.append({"unit_id": f'{plan["experiment_id"]}:exploratory:{pair:04}', "side": side, "ordinal": len(expected), "case_id": selected[pair % len(selected)], "operations": operations})
    if type(plan["runs"]) is not list or api.canonical(plan["runs"]) != api.canonical(expected):
        raise api.Failure("Measurement schedule is incomplete, altered or unbalanced")


def parameters(api, args):
    if args.stage or args.scenario_count is not None or args.scenario_case is not None:
        raise api.Failure("Measurement cases/counts come only from the explicit frozen plan")
    if not args.measurement_plan or len(args.measurement_plan) != 1:
        raise api.Failure("Measurement requires exactly one --measurement-plan")
    path = Path(args.measurement_plan[0]).resolve(strict=True)
    raw = api.read(path)
    plan = api.parse(raw)
    validate_plan(api, plan)
    return {"grid": 80, "case_ids": plan["case_ids"], "plan": plan, "plan_path": str(path), "plan_sha256": api.digest(raw)}


def sources(api, class_name, token, params):
    sources, metadata = terrain.sources(api, class_name, token, params)
    calls = []
    for run in params["plan"]["runs"]:
        name = run["case_id"]
        mode, width, height = terrain.CASES[name]
        count = len(terrain.dataset(api, name)["chunks"])
        calls.append(f'if (!RunBatch("{run["unit_id"]}", "{run["side"]}", {run["ordinal"]}, "{name}", {mode}, {width}, {height}, {run["operations"]}, {count})) return m_Result;')
    handler = api.read(api.HERE / "terrain-measurement.c.in").decode("utf-8")
    handler = handler.replace("@CLASS@", class_name).replace("@TOKEN@", token).replace("@RUN@", "\n".join(calls)).replace("@EXPECTED_RUNS@", str(len(calls)))
    sources["scripts/WorkbenchGameCommon/" + class_name + ".c"] = handler
    metadata.update(scope=SCOPE, scope_name=SCOPE_NAME, schedule_sha256=params["plan_sha256"],
                    source_templates=metadata["source_templates"], variant_mapping={"a": "preserved reference BuildRelief", "b": "direct v2 once-per-populated-band palette"},
                    paid_components=["compute", "cleanup"], excluded_components=["setup", "capture", "maintenance", "invalidation", "conversion", "cold_refresh"],
                    interpretation="single-session dependent exploratory intervals; no admission, confidence interval, physical-resource attribution or renderer-performance claim",
                    separate_semantic_receipt_required=True)
    return sources, metadata


def raw_integer(api, value):
    if not re.fullmatch(r"0|[1-9][0-9]*", value) or int(value) > 2147483647:
        raise api.Failure("Measurement contains invalid or wrapped raw integer")
    return int(value)


def validate_response(api, response, token, params):
    fields = {"schema_version", "kind", "token", "scope_name", "timer_api", "tick_unit", "executed", "failures", "expected_runs", "rows"}
    if type(response) is not dict or set(response) != fields:
        raise api.Failure("Unknown or missing measurement response fields")
    if response["token"] != token:
        raise api.Failure("Measurement token changed", "stale_input")
    if any(type(response[key]) is not int for key in ("schema_version", "executed", "failures", "expected_runs")) or response["schema_version"] != 1 or response["kind"] != "beryl.performance.target":
        raise api.Failure("Invalid measurement schema/numeric field")
    runs = params["plan"]["runs"]
    if (response["executed"] != 1 or response["failures"] != 0 or response["expected_runs"] != len(runs) or response["scope_name"] != SCOPE_NAME or response["timer_api"] != "System.GetTickCount" or response["tick_unit"] != "ms"):
        raise api.Failure("Incomplete measurement execution or incompatible timer/scope")
    rows = response["rows"]
    if type(rows) is not list or len(rows) != len(runs) + 4 or any(type(row) is not str or not row.isascii() or len(row) > 512 for row in rows):
        raise api.Failure("Incomplete or malformed measurement rows")
    previous = 0
    advances = 0
    for index, row in enumerate(rows):
        fields = row.split("|")
        if index < 4:
            if len(fields) != 4 or fields[:2] != ["timer", str(index)]:
                raise api.Failure("Timer probe framing differs")
            start, end = [raw_integer(api, value) for value in fields[2:]]
            advances += end > start
        else:
            run = runs[index - 4]
            if len(fields) != 12 or fields[:5] != ["run", run["unit_id"], run["side"], str(run["ordinal"]), run["case_id"]] or fields[7] != str(run["operations"]):
                raise api.Failure("Measurement identity/order/count differs from frozen schedule")
            start, end = raw_integer(api, fields[5]), raw_integer(api, fields[6])
            for value in fields[8:]:
                if value != "unavailable": raw_integer(api, value)
        if end < start or start < previous:
            raise api.Failure("Measurement clock reversed, wrapped or intervals overlap")
        previous = end
    if not advances:
        raise api.Failure("Timer advancement was not observed", "unavailable")
    if api.digest(api.read(params["plan_path"])) != params["plan_sha256"]:
        raise api.Failure("Measurement plan changed during execution", "stale_input")
    trace = ("\n".join(rows) + "\n").encode("ascii")
    return trace, {"events": len(rows), "runs": len(runs), "pairs": params["plan"]["pair_count"], "case_ids": params["case_ids"],
                   "sha256": api.digest(trace), "scope": SCOPE, "classification": "exploratory_target_data", "adoption_eligible": False,
                   "resolution_ms": None, "separate_semantic_receipt_required": True}
