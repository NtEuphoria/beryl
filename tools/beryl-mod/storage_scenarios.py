"""Bounded engine array and Canvas ownership observations; no pooling admission."""

ARRAY_CASES = {
    "scalar_copy_alias": [("alias-first", 99), ("copy-first", 11), ("copy-independent", 22), ("alias-cleared", 0), ("copy-count", 3)],
    "strong_copy_release": [("strong-count", 1), ("strong-same-object", 1), ("strong-shared-field", 23), ("strong-after-first-clear", 1), ("strong-no-destruction", 0), ("strong-after-last-clear", 0), ("strong-one-destruction", 1)],
    "weak_release": [("weak-count", 1), ("weak-observer-null", 0), ("weak-element-null", 1), ("weak-one-destruction", 1), ("weak-clear-no-extra-destruction", 1)],
    "nested_copy": [("nested-shared-element", 17), ("nested-independent-outer", 1), ("nested-retained-inner", 5)],
    "removal_order": [("remove-count", 3), ("remove-last-replaces", 40), ("remove-tail", 30), ("ordered-count", 3), ("ordered-shift", 30), ("ordered-tail", 40)],
    "reserve_resize_clear": [("reserve-count", 2), ("reserve-content", 8), ("resize-count", 4), ("resize-zero-first", 0), ("resize-zero-second", 0), ("clear-count", 0), ("compact-count", 0), ("reuse-content", 42), ("shrink-released", 0), ("shrink-one-destruction", 1)],
}
ARRAY_SCOPE = "Bounded scalar array Copy/alias, explicit Insert-based reference element copying and strong/weak script ownership; generic ref-array Copy is not admitted; no capacity, per-array physical memory, Canvas or pooling guarantee"
CANVAS_CASES = {
    "observer_control": [(stage + "-" + field, value) for stage, values in (("control-held", (1, 1, 1, 0)), ("control-cleared", (1, 0, 0, 1)), ("control-dropped", (0, 0, 0, 1))) for field, value in zip(("outer", "command", "vertices", "destroyed"), values)],
    "publish_replace_remove": [("workspace-present", 1), ("canvas-created", 1)] + [(stage + "-" + field, value) for stage, values in (("after-publish", (0, 0, 0, 1)), ("after-empty", (0, 0, 0, 1)), ("second-publish", (0, 0, 0, 2)), ("after-remove", (0, 0, 0, 2))) for field, value in zip(("outer", "command", "vertices", "destroyed"), values)],
}
CANVAS_SCOPE = "Immediate strong script-reference observations around real CanvasWidget SetDrawCommands, replacement and removal in owned Workbench RPC; native payload retention, rendered consumption and pooling safety unavailable"


def cases(params):
    return ARRAY_CASES if params["probe"] == "array" else CANVAS_CASES


def scope(params):
    return ARRAY_SCOPE if params["probe"] == "array" else CANVAS_SCOPE


def registry():
    return [{"name": name, "implementation": "implemented", "runtime_status": "requires execution for selected engine/artifact",
             "case_ids": list(selected), "count_parameter": "not admitted; fixed bounded operations",
             "case_selection": "nonempty unique ordered subset; default all", "evidence_scope": evidence}
            for name, selected, evidence in (("probe.array.storage", ARRAY_CASES, ARRAY_SCOPE), ("probe.canvas.retention", CANVAS_CASES, CANVAS_SCOPE))]


def parameters(api, args):
    if args.stage or args.scenario_count is not None:
        raise api.Failure("Storage probes use fixed operations; --stage/--scenario-count are not admitted")
    probe = "array" if args.scenario == "probe.array.storage" else "canvas"
    admitted = ARRAY_CASES if probe == "array" else CANVAS_CASES
    selected = args.scenario_case if args.scenario_case is not None else list(admitted)
    if not selected or len(selected) != len(set(selected)) or any(name not in admitted for name in selected):
        raise api.Failure("Storage cases must be a nonempty unique subset of " + ", ".join(admitted))
    return {"probe": probe, "case_ids": selected}


def expected(params):
    rows, checks = [], 0
    for name in params["case_ids"]:
        rows.append("case|" + name)
        for key, value in cases(params)[name]:
            rows.append(f"value|{key}|{value}")
            checks += 1
        rows.append("end|" + name)
    return rows, checks


def sources(api, class_name, token, params):
    template = api.read(api.HERE / ("array-storage.c.in" if params["probe"] == "array" else "canvas-retention.c.in")).decode("utf-8")
    calls = [f'if (!RunCase("{name}", {list(cases(params)).index(name)})) return m_Result;' for name in params["case_ids"]]
    source = template.replace("@CLASS@", class_name).replace("@TOKEN@", token).replace("@RUN@", "\n".join(calls))
    return {"scripts/WorkbenchGameCommon/" + class_name + ".c": source}, {
        "scope": scope(params), "observer": "weak class fields; helper scopes release strong local temporaries",
        "physical_memory": "unavailable in semantic receipt; logical counts do not imply capacity or physical release",
        "native_consumer_lifetime": "unavailable: no rendered frame/readback or native retention guarantee established",
        "pooling_admission": "unavailable"}


def validate_response(api, response, token, params):
    import scenarios
    wanted, checks = expected(params)
    rows, checksum = scenarios.validate_wire(api, response, token, params["case_ids"], checks, len(wanted))
    if rows != wanted:
        raise api.Failure("Storage ownership observation differs from the admitted contract")
    trace = ("\n".join(rows) + "\n").encode("ascii")
    return trace, {"checks": checks, "events": len(rows), "case_ids": params["case_ids"], "checksum": checksum,
                   "checksum_algorithm": "polynomial31_mod1000003_ascii_lf", "sha256": api.digest(trace), "scope": scope(params)}
