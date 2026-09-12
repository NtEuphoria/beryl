"""Strict completeness checks for the private schema-4 probe's exact JSON shape."""
import copy


class InvalidProbe(ValueError):
    pass


PROCESS_NAMES = ("ast-O0", "ast-O2", "ir-O0", "ir-O2")
STATUS = {"IR_RUN_SUCCESS": 0, "IR_RUN_FAILED": 1, "IR_RUN_TRAP": 2, "IR_RUN_BUDGET": 3}
REFERENCE_STATUS = {"IR_RUN_SUCCESS": 0, "IR_RUN_FAILED": 1, "IR_RUN_TRAP": 3, "IR_RUN_BUDGET": 4}
COUNTERS = {"reference_status", "reference_trap", "reference_steps", "ir_status", "ir_trap", "ir_steps", "tests", "assertions", "mutants_rejected"}
FIELDS = COUNTERS | {"reference_complete", "ir_complete", "processes"}
EXECUTED = {"name", "compile_status", "compile_exit", "run_status", "run_exit"}
SKIPPED = "outside AST-C admitted execution domain"


def integer(value, name, maximum=2**64-1):
    if type(value) is not int or not 0 <= value <= maximum:
        raise InvalidProbe("invalid unsigned integer: " + name)


def validate_probe(value, expected_status, expected_assertions, expected_tests=1):
    if type(value) is not dict or set(value) != FIELDS:
        raise InvalidProbe("missing or unknown probe receipt fields")
    if expected_status not in STATUS:
        raise InvalidProbe("unknown expected semantic status")
    integer(expected_assertions, "expected assertions")
    integer(expected_tests, "expected tests")
    for name in sorted(COUNTERS):
        integer(value[name], name)
    for name in ("reference_complete", "ir_complete"):
        if type(value[name]) is not bool:
            raise InvalidProbe("expected exact boolean: " + name)
    if value["ir_status"] != STATUS[expected_status] or value["reference_status"] != REFERENCE_STATUS[expected_status]:
        raise InvalidProbe("semantic status does not match the selected fixture")
    if value["reference_trap"] > 3 or value["ir_trap"] > 3:
        raise InvalidProbe("unknown trap category")
    if value["assertions"] != expected_assertions or value["tests"] != expected_tests:
        raise InvalidProbe("missing or unexpected fixture assertions/tests")
    if value["mutants_rejected"] != 6:
        raise InvalidProbe("all six emitter admission mutants must execute and reject")
    processes = value["processes"]
    if type(processes) is not list or len(processes) != len(PROCESS_NAMES):
        raise InvalidProbe("exactly four compiler/execution rows are required")
    if any(type(row) is not dict or type(row.get("name")) is not str for row in processes):
        raise InvalidProbe("invalid process row or name")
    names = [row["name"] for row in processes]
    if len(set(names)) != len(names) or set(names) != set(PROCESS_NAMES):
        raise InvalidProbe("missing, duplicate or unknown compiler/execution name")
    outside_ast = (expected_status == "IR_RUN_TRAP" and value["ir_trap"] == 0) or expected_status == "IR_RUN_BUDGET"
    for row in processes:
        if outside_ast and row["name"].startswith("ast-"):
            if set(row) != {"name", "skipped"} or row["skipped"] != SKIPPED:
                raise InvalidProbe("outside-domain AST row requires its exact explicit skip")
            continue
        if set(row) != EXECUTED:
            raise InvalidProbe("missing or unknown compilation/execution fields")
        for field in sorted(EXECUTED - {"name"}):
            integer(row[field], row["name"] + "." + field, 2**32-1)
        if row["compile_status"] != 0 or row["compile_exit"] != 0 or row["run_status"] != 0:
            raise InvalidProbe("compile or execution did not complete successfully")
        if expected_status == "IR_RUN_SUCCESS" and row["run_exit"] != 0:
            raise InvalidProbe("successful fixture returned nonzero")
        if expected_status == "IR_RUN_FAILED" and row["run_exit"] != 1:
            raise InvalidProbe("assertion-failure fixture returned unexpected status")
        if expected_status in ("IR_RUN_TRAP", "IR_RUN_BUDGET") and row["run_exit"] == 0:
            raise InvalidProbe("trap/budget fixture unexpectedly returned success")
    return outside_ast


def selftest():
    """Synthetic malformed receipt checks; these execute no compiler/program."""
    good = {"reference_status": 0, "reference_trap": 0, "reference_complete": False, "reference_steps": 9,
            "ir_status": 0, "ir_trap": 0, "ir_complete": False, "ir_steps": 7,
            "tests": 1, "assertions": 2, "mutants_rejected": 6,
            "processes": [{"name": name, "compile_status": 0, "compile_exit": 0, "run_status": 0, "run_exit": 0} for name in PROCESS_NAMES]}
    validate_probe(good, "IR_RUN_SUCCESS", 2)
    checks = ["complete successful four-process receipt"]
    mutants = []
    def add(name, edit):
        value = copy.deepcopy(good); edit(value); mutants.append((name, value))
    add("empty process list", lambda v: v.update(processes=[]))
    add("missing process", lambda v: v["processes"].pop())
    add("duplicate process", lambda v: v["processes"][1].update(name="ast-O0"))
    add("unknown process", lambda v: v["processes"][1].update(name="native-O3"))
    add("unknown row field", lambda v: v["processes"][0].update(extra=1))
    add("unexpected skipped execution", lambda v: v["processes"].__setitem__(0, {"name": "ast-O0", "skipped": SKIPPED}))
    for field in sorted(EXECUTED - {"name"}):
        add("missing " + field, lambda v, f=field: v["processes"][0].pop(f))
        add("boolean " + field, lambda v, f=field: v["processes"][0].update({f: False}))
    for field in sorted(COUNTERS):
        add("boolean " + field, lambda v, f=field: v.update({f: True if f == "tests" else False}))
    add("missing mutant count", lambda v: v.pop("mutants_rejected"))
    for number in (5, 7, 6.0, "6", None, True):
        add("non-exact mutant count " + repr(number), lambda v, n=number: v.update(mutants_rejected=n))
    add("missing whole receipt field", lambda v: v.pop("reference_complete"))
    add("unknown whole receipt field", lambda v: v.update(extra=1))
    add("incomplete compile", lambda v: v["processes"][0].update(compile_status=1))
    add("incomplete run", lambda v: v["processes"][0].update(run_status=1))
    for name, mutant in mutants:
        try:
            validate_probe(mutant, "IR_RUN_SUCCESS", 2)
        except InvalidProbe:
            checks.append(name)
        else:
            raise AssertionError("malformed receipt accepted: " + name)
    skipped = copy.deepcopy(good)
    skipped.update(reference_status=4, ir_status=3, assertions=0)
    skipped["processes"] = [{"name": name, "skipped": SKIPPED} if name.startswith("ast-") else
                             {"name": name, "compile_status": 0, "compile_exit": 0, "run_status": 0, "run_exit": 3} for name in PROCESS_NAMES]
    validate_probe(skipped, "IR_RUN_BUDGET", 0)
    checks.append("exact outside-domain AST skips retain both executed IR rows")
    skipped["processes"][2] = {"name": "ir-O0", "skipped": SKIPPED}
    try:
        validate_probe(skipped, "IR_RUN_BUDGET", 0)
    except InvalidProbe:
        checks.append("IR execution cannot be skipped")
    else:
        raise AssertionError("missing IR execution accepted")
    return checks
