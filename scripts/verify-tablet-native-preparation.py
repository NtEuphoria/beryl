#!/usr/bin/env python3
"""Pure source/receipt/fixture faults for tablet native preparation; no execution."""
from pathlib import Path
import copy
import importlib.util
import json
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/prepare-tablet-native-callbacks.py"


def load():
    spec = importlib.util.spec_from_file_location("tablet_native_prepare_inert", SOURCE)
    value = importlib.util.module_from_spec(spec)
    exec(compile(SOURCE.read_bytes(), str(SOURCE), "exec"), value.__dict__)
    return value


def main():
    m = load()
    work = Path(tempfile.mkdtemp(prefix="tablet native preparation inert & spaces-", dir=ROOT / "build"))
    record = {"schema_version": 1, "operation": "verify.tablet_native_preparation.inert", "status": "failure",
              "scope": {"python": "pure_source_and_owned_file_validation", "new_preparation_main": "not_run",
                        "compiler": "not_run", "host": "not_run", "engine": "not_run", "native_callbacks": "not_run",
                        "process_signals": "not_run", "live_writes": "not_run"}, "cases": [], "failures": []}
    contract, assets = m.package_inputs()
    source_raw = m.mod.read(m.DEFAULT_RECEIPT)
    prior = m.mod.parse(source_raw)
    mapping = m.mod.parse(m.mod.read(Path(prior["generated_source_map"]["path"])))
    generated = m.mod.read(Path(prior["candidate_path"]) / prior["generated_file"])
    production = m.mod.read(Path(prior["candidate_path"]) / m.s1.TABLET)
    template = assets["observer.c.in"]
    source_payloads = {m.s1.TABLET: production, prior["generated_file"]: generated}
    observer, symbols, origins = m.render_observer(mapping, generated, production, template)
    tests = []
    def add(name, action, rejection=False):
        tests.append((name, action, rejection))
    def mutate_contract(key, value):
        changed = copy.deepcopy(contract)
        changed[key] = value
        return m.validate_contract(changed)
    def mutate_mapping(action):
        changed = copy.deepcopy(mapping)
        action(changed)
        return m.render_observer(changed, generated, production, template)
    add("contract.current", lambda: m.validate_contract(contract))
    add("contract.schema-bool", lambda: mutate_contract("schema_version", True), True)
    add("contract.schema-missing", lambda: m.validate_contract({k: v for k,v in contract.items() if k != "schema_version"}), True)
    add("contract.unknown-field", lambda: mutate_contract("unknown", True), True)
    add("contract.wrong-profile", lambda: mutate_contract("profile", "other"), True)
    add("contract.runtime-claim", lambda: mutate_contract("state", "runtime_verified"), True)
    add("assets.current", lambda: m.admit_assets(contract, assets))
    for name in sorted(assets):
        add("assets.missing." + name, lambda name=name: m.admit_assets(contract, {k:v for k,v in assets.items() if k != name}), True)
        add("assets.changed." + name, lambda name=name: m.admit_assets(contract, dict(assets, **{name: assets[name] + b"x"})), True)
    add("assets.extra", lambda: m.admit_assets(contract, dict(assets, unexpected=b"x")), True)
    add("assets.nonbytes", lambda: m.admit_assets(contract, dict(assets, **{"observer.c.in": "text"})), True)
    add("receipt.current-shape", lambda: m.prior_guard.validate_source_receipt(prior))
    for key,value in (("schema_version",True),("status","failure"),("stage","runtime"),("candidate_profile","other")):
        def action(key=key,value=value):
            changed=copy.deepcopy(prior);changed[key]=value
            return m.prior_guard.validate_source_receipt(changed)
        add("receipt."+key, action, True)
    add("render.current", lambda: m.render_observer(mapping, generated, production, template))
    add("render.deterministic", lambda: check(m.render_observer(mapping, generated, production, template) == (observer,symbols,origins), "Nondeterministic source/origins"))
    add("render.source-preserved", lambda: check(production == m.s1.render(mapping, generated)[0], "Adapter mismatch"))
    add("render.unknown-template-field", lambda: m.render_observer(mapping, generated, production, template+b"\n@UNKNOWN@\n"), True)
    add("render.changed-production", lambda: m.render_observer(mapping, generated, production+b"x", template), True)
    add("render.changed-signature", lambda: m.render_observer(mapping, generated.replace(b"static int ",b"static bool "),production,template), True)
    add("render.schema-bool", lambda: mutate_mapping(lambda x:x.update(schema_version=True)), True)
    add("render.linkage-schema-bool", lambda: mutate_mapping(lambda x:x.update(linkage_schema_version=True)), True)
    add("render.missing-linkage", lambda: mutate_mapping(lambda x:x.pop("linkage")), True)
    def state_row(x):
        return next(row for row in x["linkage"] if row["declaration"]=="sparkos.tablet_lifecycle_prototype.State")
    add("render.duplicate-state", lambda: mutate_mapping(lambda x:x["linkage"].append(copy.deepcopy(state_row(x)))), True)
    add("render.missing-accumulator", lambda: mutate_mapping(lambda x:state_row(x).update(fields=[f for f in state_row(x)["fields"] if f["source"]!="telemetry_accumulator"])), True)
    add("render.invalid-field-name", lambda: mutate_mapping(lambda x:state_row(x)["fields"][0].update(name="bad name")), True)
    add("render.extra-state-field", lambda: mutate_mapping(lambda x:state_row(x)["fields"].append({"source":"extra","name":"field"})), True)
    add("render.origin-complete", lambda: check([x["generated_line"] for x in origins] == [i for i,l in enumerate(observer.decode().splitlines(),1) if l.strip()], "Incomplete origin map"))
    add("identities.current", lambda: m.validate_identity_collisions(source_payloads,observer,assets))
    for name in m.NAMES:
        add("identities.class-collision."+name, lambda name=name: m.validate_identity_collisions(dict(source_payloads, **{"other.c": ("class "+name.lower()+" {}\n").encode()}), observer,assets), True)
    add("identities.second-production", lambda: m.validate_identity_collisions(dict(source_payloads, **{"second.c":production}),observer,assets), True)
    add("identities.no-production", lambda: m.validate_identity_collisions({prior["generated_file"]:generated},observer,assets), True)
    add("identities.fixture-path-collision", lambda: m.validate_identity_collisions(dict(source_payloads, **{m.ASSETS[0]:b"x"}),observer,assets), True)
    add("identities.resource-guid-collision", lambda: m.validate_identity_collisions(dict(source_payloads, **{"old.meta":assets[m.ASSETS[1]]}),observer,assets), True)
    add("identities.casefold-guid-collision", lambda: m.validate_identity_collisions(dict(source_payloads, **{"old.meta":assets[m.ASSETS[1]].lower()}),observer,assets), True)
    add("project.fixed-base-only", lambda: check(m.candidate_project(contract) == b'GameProject {\n ID "BerylTabletNativeStowedPrototype"\n GUID "BE71570020261010"\n TITLE "Beryl experimental native tablet init and stowed frames"\n Dependencies {\n  "58D0FB3206B6F859"\n }\n}\n', "Wrong typed candidate project"))
    add("scope.proposed-cases-not-runtime", lambda: check(contract["fixture"]["runtime_case_state"]=="proposed_not_installed" and contract["admission_limits"]["runtime"].startswith("unavailable"), "Runtime scope mismatch"))
    target=work/"owned-tree";m.write(target/"nested/a.c",b"a");m.write(target/"b.meta",b"b")
    table=m.h.files(target)
    add("tree.exact",lambda:m.prior_guard.checked_tree(target,table))
    def changed_tree():
        m.write(target/"nested/a.c",b"x")
        try:return m.prior_guard.checked_tree(target,table)
        finally:m.write(target/"nested/a.c",b"a")
    add("tree.changed-bytes",changed_tree,True)
    def extra_tree():
        m.write(target/"extra.c",b"x")
        try:return m.prior_guard.checked_tree(target,table)
        finally:(target/"extra.c").unlink()
    add("tree.extra-file",extra_tree,True)
    def extra_dir():
        (target/"empty").mkdir()
        try:return m.prior_guard.checked_tree(target,table)
        finally:(target/"empty").rmdir()
    add("tree.extra-empty-dir",extra_dir,True)
    add("budget.two-owner-records", lambda:check(4+4*contract["fixture"]["maximum_frames_per_owner"] <= contract["fixture"]["row_limit"], "Declared frame budget exceeds observation rows"))
    expected=[name for name,_,_ in tests]
    check(len(expected)==len(set(expected)),"Duplicate planned case IDs")
    record["expected_case_ids"]=expected
    record["expected_cases"]=len(expected)
    inputs=[Path(__file__).resolve(),SOURCE,m.GUARD,Path(m.s1.__file__),Path(m.h.__file__),Path(m.mod.__file__),m.DEFAULT_RECEIPT,
            Path(prior["generated_source_map"]["path"]),Path(prior["candidate_path"])/prior["generated_file"],Path(prior["candidate_path"])/m.s1.TABLET]
    inputs += sorted(p for p in m.PACKAGE.rglob("*") if p.is_file())
    tracked={str(p):m.identity(p) for p in inputs}
    for i,p in enumerate(inputs):m.write(work/"inputs"/(str(i).zfill(3)+"-"+p.name),m.mod.read(p))
    record["verification_inputs"]=tracked
    m.h.save_result(work/"result.json",record)
    (work/"cases").mkdir()
    for name,action,rejection in tests:
        item={"id":name,"status":"failure","expected_outcome":"rejection" if rejection else "success"}
        try:
            action()
            check(not rejection,"Expected admission rejection was absent")
            item["status"]="success"
        except m.mod.Failure as error:
            item["actual_rejection"]={"type":type(error).__name__,"status":error.status,"message":str(error)}
            if rejection:item["status"]="success"
        except BaseException as error:
            item["error"]={"type":type(error).__name__,"message":str(error)}
        record["cases"].append(item)
        if item["status"]!="success":record["failures"].append(name)
        m.h.save_result(work/"cases"/(str(len(record["cases"])).zfill(3)+".json"),item)
    record["source_unchanged"]={str(p):m.identity(p) for p in inputs}==tracked
    check(record["source_unchanged"],"Frozen test input changed")
    record["completed_case_ids"]=[case["id"] for case in record["cases"]]
    check(record["completed_case_ids"]==expected,"Executed case set differs from predeclared set")
    record["retained_input_files"]=m.h.files(work/"inputs")
    record["passed"]=len(expected)-len(record["failures"])
    record["failed"]=len(record["failures"])
    record["status"]="success" if not record["failures"] else "failure"
    m.h.save_result(work/"result.json",record)
    print(json.dumps({"path":str(work/"result.json"),"sha256":m.identity(work/"result.json")["sha256"],"expected":len(expected),"passed":record["passed"],"failed":record["failed"],"failures":record["failures"]}),flush=True)
    return 0 if record["status"]=="success" else 1


def check(condition,message):
    if not condition:raise AssertionError(message)


if __name__=="__main__":
    raise SystemExit(main())
