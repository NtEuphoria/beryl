#!/usr/bin/env python3
"""Bounded local MCP stdio adapter over the Beryl CLI; no model or HTTP service.

The trusted launcher fixes the compiler and project. Tool parameters cannot
select executables, command lines, Python modules, or project build hooks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import threading
import time
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from process_job import ProcessJob

PROTOCOL = "2025-11-25"
MAX_FRAME = 12 * 1024 * 1024
MAX_OUTPUT = 4 * 1024 * 1024
MAX_IDS = 4096


class Invalid(ValueError):
    pass


class Unavailable(Invalid):
    pass


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise Invalid("duplicate JSON key: " + key)
        result[key] = value
    return result


def encode(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def decode(raw):
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                       parse_constant=lambda x: (_ for _ in ()).throw(Invalid("nonfinite JSON")))
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if depth > 64 or count > 262144:
            raise Invalid("JSON depth or value limit exceeded")
        if isinstance(item, dict):
            pending.extend((v, depth + 1) for v in item.values())
            pending.extend((v, depth + 1) for v in item.keys())
        elif isinstance(item, list):
            pending.extend((v, depth + 1) for v in item)
        elif isinstance(item, str):
            item.encode("utf-8", errors="strict")
        elif type(item) is float and not math.isfinite(item):
            raise Invalid("nonfinite JSON")
    return value


def obj(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


TEXT = {"type": "string", "minLength": 1, "maxLength": 1024}
SOURCES = {"type": "array", "items": TEXT, "maxItems": 64, "uniqueItems": True}


def tool(name, description, schema, read_only):
    return {"name": name, "description": description, "inputSchema": schema,
            "annotations": {"readOnlyHint": read_only, "destructiveHint": False,
                            "idempotentHint": read_only, "openWorldHint": False}}


TOOLS = [
    tool("beryl_context", "Read actual project, capability, example, symbol, binding or optimization context. Does not execute Beryl or launch an engine.",
         obj({"topic": {"enum": ["project", "capabilities", "examples", "symbol", "binding", "optimization"]},
              "name": TEXT, "sources": SOURCES}, ("topic",)), True),
    tool("beryl_doctor", "Inventory the local environment. Only explicit probe=native compiles and executes a fixed C11 readiness fixture; it does not run project code.",
         obj({"probe": {"enum": ["native"]}}), False),
    tool("beryl_analyze", "Analyze an exact supplied source snapshot through the C analyzer. request is the version-1 analysis request; contents maps every content_file to its exact UTF-8 text. Never substitutes a disk source.",
         obj({"request": {"type": "object"}, "contents": {"type": "object", "additionalProperties": {"type": "string"}}}, ("request", "contents")), True),
    tool("beryl_test", "Explicitly execute selected Beryl tests using the chosen backend. May compile/run native project code. Source paths must be project-relative .be files.",
         obj({"sources": {**SOURCES, "minItems": 1}, "backend": {"enum": ["reference", "native", "differential"]}}, ("sources", "backend")), False),
    tool("beryl_mod", "Call installed typed mod operations. plan describes a structurally validated v1 workflow without compiler or engine execution; it does not verify source semantics. verify executes compilation or an explicitly selected installed scenario against an artifact. No promotion is exposed by this adapter.",
         obj({"operation": {"enum": ["plan", "check", "build", "verify", "scenarios"]}, "artifact": {"type": "string", "pattern": "^[0-9a-f]{32}$"},
              "stage": {"enum": ["compile"]}, "scenario": TEXT}, ("operation",)), False),
    tool("beryl_evidence", "Read a bounded project-relative JSON receipt or source-map file and its content hash. Reading a receipt does not validate its claims or applicability.",
         obj({"path": TEXT}, ("path",)), True),
]
TOOL_BY_NAME = {v["name"]: v for v in TOOLS}


def validate(value, schema):
    kind = schema.get("type")
    if kind and type(value) is not {"object": dict, "array": list, "string": str}[kind]:
        raise Invalid("expected " + kind)
    if "enum" in schema and value not in schema["enum"]:
        raise Invalid("unsupported selection")
    if isinstance(value, dict) and "properties" in schema:
        if set(value) - set(schema["properties"]) or set(schema["required"]) - set(value):
            raise Invalid("unknown or missing tool parameter")
        for key, child in value.items():
            validate(child, schema["properties"][key])
    elif isinstance(value, dict) and isinstance(schema.get("additionalProperties"), dict):
        for child in value.values():
            validate(child, schema["additionalProperties"])
    elif isinstance(value, list):
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 64):
            raise Invalid("array outside admitted limit")
        if schema.get("uniqueItems") and len({encode(v) for v in value}) != len(value):
            raise Invalid("duplicate array item")
        for child in value:
            validate(child, schema["items"])
    elif isinstance(value, str):
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", MAX_FRAME):
            raise Invalid("string outside admitted limit")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            raise Invalid("invalid string format")


def parts(name):
    if type(name) is not str or not name or len(name.encode("utf-8")) > 1024:
        raise Invalid("expected bounded project-relative path")
    if any(ord(c) < 32 or c in '\\:<>|?*"' or ord(c) == 127 for c in name):
        raise Invalid("unsupported path character")
    values = name.split("/")
    for item in values:
        if item in ("", ".", "..") or item.endswith((" ", ".")):
            raise Invalid("path traversal or ambiguous segment")
        if re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", item.split(".")[0]):
            raise Invalid("device path is unsupported")
    return values


def safe_path(root, name, existing=True):
    path = root
    for part in parts(name):
        path = path / part
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise Invalid("linked project paths are unsupported")
    if existing and not path.is_file():
        raise Invalid("missing project file: " + name)
    if not path.resolve().is_relative_to(root):
        raise Invalid("path escapes project")
    return path


def read(path, maximum=MAX_OUTPUT):
    with path.open("rb") as handle:
        meta = os.fstat(handle.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
            raise Invalid("expected regular unshared file")
        data = handle.read(maximum + 1)
    if len(data) > maximum:
        raise Invalid("file exceeds admitted limit")
    return data


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Server:
    def __init__(self, compiler, project, timeout, workbench_tools=None):
        self.compiler, self.project, self.timeout = compiler, project, timeout
        self.workbench_tools = workbench_tools
        self.compiler_hash = digest(read(compiler, 128 * 1024 * 1024))
        self.output_lock, self.state_lock = threading.Lock(), threading.Lock()
        self.initialized = False
        self.negotiated = False
        self.ids = set()
        self.active = None

    def send(self, value):
        with self.output_lock:
            sys.stdout.buffer.write(encode(value).encode("utf-8") + b"\n")
            sys.stdout.buffer.flush()

    def error(self, identity, code, message):
        self.send({"jsonrpc": "2.0", "id": identity, "error": {"code": code, "message": message}})

    def result(self, identity, value):
        self.send({"jsonrpc": "2.0", "id": identity, "result": value})

    def job(self):
        path = safe_path(self.project, ".beryl-mcp/jobs/" + uuid.uuid4().hex, False)
        path.mkdir(parents=True, exist_ok=False)
        return path

    def command(self, name, args, job):
        sources = [safe_path(self.project, value) for value in args.get("sources", [])]
        if any(p.suffix != ".be" for p in sources):
            raise Invalid("source paths must end with .be")
        if len({str(p).lower() for p in sources}) != len(sources):
            raise Invalid("ambiguous duplicate source identity")
        argv = [str(self.compiler)]
        if name == "beryl_context":
            topic, symbol = args["topic"], args.get("name")
            if topic in ("symbol", "binding") and not symbol:
                raise Invalid("this context topic requires name")
            if topic == "symbol" and not sources:
                raise Invalid("symbol context requires explicit sources")
            if topic in ("project", "capabilities", "examples") and symbol:
                raise Invalid("name is unsupported for this topic")
            if topic in ("capabilities", "examples", "binding") and sources:
                raise Invalid("sources are unsupported for this topic")
            if symbol and (symbol.startswith("-") or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9.]*", symbol)):
                raise Invalid("expected a qualified declaration or binding name")
            argv += ["context", topic]
            if symbol:
                argv.append(symbol)
            elif topic == "optimization":
                if sources:
                    raise Invalid("optimization list does not accept sources")
                argv.append("--list")
            argv += [str(p) for p in sources]
        elif name == "beryl_doctor":
            argv += ["doctor", "--format", "json"]
            if args.get("probe"):
                argv += ["--probe", args["probe"]]
        elif name == "beryl_analyze":
            request, contents = args["request"], args["contents"]
            if type(request.get("sources")) is not list or not 1 <= len(request["sources"]) <= 64:
                raise Invalid("analysis request requires 1..64 sources")
            expected = []
            total = 0
            for source in request["sources"]:
                if type(source) is not dict or type(source.get("content_file")) is not str:
                    raise Invalid("missing analysis content_file")
                filename = source["content_file"]
                if len(parts(filename)) != 1 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", filename):
                    raise Invalid("analysis content_file must be a safe adjacent basename")
                if filename not in contents or filename.lower() in expected:
                    raise Invalid("missing or duplicate supplied overlay")
                expected.append(filename.lower())
                data = contents[filename].encode("utf-8")
                total += len(data)
                if len(data) > 1024 * 1024 or total > 8 * 1024 * 1024:
                    raise Invalid("analysis source budget exceeded")
            if len(contents) != len(expected):
                raise Invalid("unselected analysis content")
            request_dir = job / "request"
            request_dir.mkdir()
            for filename, content in contents.items():
                with (request_dir / filename).open("xb") as output:
                    output.write(content.encode("utf-8"))
            if (request_dir / "request.json").exists():
                raise Invalid("reserved analysis request basename")
            request_file = request_dir / "request.json"
            encoded = encode(request).encode("utf-8")
            if len(encoded) > 1024 * 1024:
                raise Invalid("analysis request exceeds 1 MiB")
            with request_file.open("xb") as output:
                output.write(encoded)
            argv += ["analyze", "--request", str(request_file)]
        elif name == "beryl_test":
            argv += ["test", "--backend", args["backend"], *map(str, sources)]
        elif name == "beryl_mod":
            op = args["operation"]
            if op == "verify":
                if not args.get("artifact") or bool(args.get("stage")) == bool(args.get("scenario")):
                    raise Invalid("verify requires artifact and exactly one of stage or scenario")
                if args.get("scenario") and not re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", args["scenario"]):
                    raise Invalid("expected installed scenario name")
            elif set(args) != {"operation"}:
                raise Invalid("only verify accepts artifact/stage/scenario")
            argv += ["mod", op, "--project", str(self.project)]
            if op == "verify":
                if not self.workbench_tools:
                    raise Unavailable("engine verification requires the launcher's --workbench-tools configuration")
                argv += ["--workbench-tools", str(self.workbench_tools)]
            for key in ("artifact", "stage", "scenario"):
                if key in args:
                    argv += ["--" + key, args[key]]
        else:
            raise Invalid("unsupported command tool")
        return argv, sources

    def execute(self, name, args, cancel):
        report = {"schema_version": 1, "operation": name, "stage": "adapter", "status": "failure",
                  "compiler_sha256": self.compiler_hash, "execution": "not_run", "result": None,
                  "exit_code": None, "raw_logs": [], "measurements": None}
        try:
            if cancel.is_set():
                report["status"] = "cancelled"
                return report
            if digest(read(self.compiler, 128 * 1024 * 1024)) != self.compiler_hash:
                report["status"] = "stale_input"
                return report
            if name == "beryl_evidence":
                path = safe_path(self.project, args["path"])
                if path.suffix != ".json":
                    raise Invalid("evidence must be a JSON file")
                data = read(path)
                report.update(status="success", result=decode(data), evidence_sha256=digest(data),
                              applicability="not_checked", path=str(path))
                return report
            job = self.job()
            report["receipt"] = str(job / "result.json")
            argv, sources = self.command(name, args, job)
            before = {str(p): digest(read(p)) for p in sources}
            report.update(argv=argv, source_hashes=before, stage="cli")
            outpath, errpath = job / "stdout.log", job / "stderr.log"
            report["raw_logs"] = [str(outpath), str(errpath)]
            exceeded, io_error = threading.Event(), threading.Event()

            def drain(pipe, path):
                try:
                    remaining = MAX_OUTPUT
                    with path.open("xb") as stream:
                        while True:
                            data = pipe.read(65536)
                            if not data:
                                break
                            accepted = min(remaining, len(data))
                            stream.write(data[:accepted])
                            remaining -= accepted
                            if accepted != len(data):
                                exceeded.set()
                                break
                except (OSError, ValueError):
                    io_error.set()
                finally:
                    pipe.close()

            with ProcessJob() as owner:
                process = subprocess.Popen(argv, cwd=self.project, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           creationflags=owner.flags, start_new_session=(os.name != "nt"))
                owner.attach(process)
                report["execution"] = "cli_started"
                readers = [threading.Thread(target=drain, args=(pipe, path), daemon=True)
                           for pipe, path in ((process.stdout, outpath), (process.stderr, errpath))]
                for reader in readers:
                    reader.start()
                started = time.monotonic()
                status = None
                while process.poll() is None:
                    if cancel.is_set():
                        status = "cancelled"
                    elif exceeded.is_set():
                        status = "output_limit"
                    elif io_error.is_set():
                        status = "io_failure"
                    elif time.monotonic() - started >= self.timeout:
                        status = "timeout"
                    if status:
                        owner.stop(process)
                        break
                    time.sleep(0.01)
                # Stop descendants even after a normal exit before joining pipe readers.
                owner.stop(process)
                for reader in readers:
                    reader.join(timeout=10)
                if any(r.is_alive() for r in readers):
                    status = "io_failure"
                report["exit_code"] = process.returncode
            if cancel.is_set():
                status = "cancelled"
            elif exceeded.is_set():
                status = "output_limit"
            elif io_error.is_set():
                status = "io_failure"
            if status:
                report["status"] = status
            elif digest(read(self.compiler, 128 * 1024 * 1024)) != self.compiler_hash or any(digest(read(p)) != before[str(p)] for p in sources):
                report["status"] = "stale_input"
            else:
                stdout = read(outpath)
                report["status"] = "success" if process.returncode == 0 else "failure"
                if name == "beryl_test":
                    report["result"] = {"stdout": stdout.decode("utf-8", errors="replace"), "interpretation": "CLI exit status; retain native/reference receipts for detailed outcomes"}
                else:
                    try:
                        report["result"] = decode(stdout)
                        self.validate_response(name, args, report["result"], job)
                        if report["result"]["status"] != "success":
                            report["status"] = report["result"]["status"]
                    except (ValueError, UnicodeError, RecursionError):
                        report.update(status="invalid_response", result=None)
        except (Invalid, OSError, ValueError, RecursionError, subprocess.SubprocessError) as exc:
            report.update(status="cancelled" if cancel.is_set() else "unavailable" if isinstance(exc, Unavailable) else "failure", result=None, error=str(exc))
        return report

    def validate_response(self, name, args, value, job):
        if type(value) is not dict or type(value.get("schema_version")) is not int or value["schema_version"] != 1 or type(value.get("status")) is not str:
            raise Invalid("missing versioned CLI status envelope")
        expected = "context." + args["topic"] if name == "beryl_context" else "doctor" if name == "beryl_doctor" else "analyze" if name == "beryl_analyze" else "mod " + args["operation"]
        if value.get("operation") != expected:
            # The existing mod argument-failure envelope predates per-command jobs.
            if not (name == "beryl_mod" and value.get("operation") == "mod" and value["status"] != "success"):
                raise Invalid("CLI operation identity does not match request")
        if value["status"] != "success":
            return
        if name in ("beryl_context", "beryl_doctor", "beryl_analyze"):
            if value.get("compiler_fingerprint") != self.compiler_hash:
                raise Invalid("missing or mismatched compiler identity")
        elif args["operation"] != "scenarios" and value.get("compiler_sha256") != self.compiler_hash:
            raise Invalid("mod compiler identity does not match request")
        if name == "beryl_analyze":
            request = args["request"]
            received = value.get("sources")
            if type(value.get("snapshot_version")) is not int or type(received) is not list or any(
                    type(f) is not dict or type(f.get("file_id")) is not int or
                    type(f.get("document_version")) is not int or type(f.get("path")) is not str or
                    type(f.get("sha256")) is not str for f in received):
                raise Invalid("analysis response descriptor types are invalid")
            expected_sources = [{"path": f["path"], "sha256": f["sha256"],
                                 "document_version": f["document_version"], "file_id": i}
                                for i, f in enumerate(request["sources"])]
            if value.get("request_id") != request.get("request_id") or value.get("snapshot_version") != request.get("snapshot_version") or value.get("sources") != expected_sources:
                raise Invalid("analysis response does not identify the supplied snapshot")
            if value.get("request_fingerprint") != digest(read(job / "request/request.json")):
                raise Invalid("analysis request fingerprint mismatch")
            for key in ("snapshot_fingerprint", "source_fingerprint"):
                if type(value.get(key)) is not str or not re.fullmatch("[0-9a-f]{64}", value[key]):
                    raise Invalid("missing analysis snapshot identity")
            if value.get("execution") != "not_run" or type(value.get("admission")) is not dict or value["admission"].get("target") != request["target"]:
                raise Invalid("analysis result has an incompatible execution or target contract")
        if name == "beryl_context" and value.get("execution") != "not_run":
            raise Invalid("context result cannot claim program execution")
        if name == "beryl_mod" and args["operation"] == "plan":
            plan = value.get("plan")
            if value.get("execution") != "not_run" or type(plan) is not dict or plan.get("kind") != "beryl.mod.workflow" or type(plan.get("schema_version")) is not int or plan["schema_version"] != 1:
                raise Invalid("mod plan response has an incompatible execution or workflow contract")
            identity = digest(json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode())
            if value.get("plan_sha256") != identity:
                raise Invalid("mod plan content identity differs")
            identities, admission = plan.get("identities"), plan.get("admission")
            if type(identities) is not dict or type(admission) is not dict or identities.get("compiler_sha256") != self.compiler_hash or admission.get("structure") != "validated":
                raise Invalid("mod plan is missing compiler identity or structural validation")
            if admission.get("symbols") != "not_checked" or admission.get("target_semantics") != "not_checked" or value.get("artifact_sha256") is not None:
                raise Invalid("mod plan cannot claim source admission or an executed artifact")

    def worker(self, identity, name, args, cancel):
        try:
            report = self.execute(name, args, cancel)
        except Exception as exc:
            report = {"schema_version": 1, "operation": name, "stage": "adapter",
                      "status": "internal_error", "result": None, "error": str(exc)}
        with self.state_lock:
            try:
                if cancel.is_set():
                    report.update(status="cancelled", result=None)
                # MCP duplicates structured results as text for client compatibility.
                # Bound the complete outgoing frame as well as each raw child log.
                preview = {"jsonrpc": "2.0", "id": identity, "result": {
                    "content": [{"type": "text", "text": encode(report)}],
                    "structuredContent": report, "isError": report["status"] != "success"}}
                if len(encode(preview)) + 1 > MAX_FRAME:
                    report.update(status="output_limit", result=None,
                                  error="encoded protocol response exceeds frame limit; inspect bounded raw logs")
                if report.get("receipt"):
                    try:
                        with Path(report["receipt"]).open("x", encoding="utf-8") as output:
                            output.write(encode(report) + "\n")
                    except OSError as exc:
                        report.update(status="io_failure", result=None, error=str(exc))
                self.result(identity, {"content": [{"type": "text", "text": encode(report)}],
                                       "structuredContent": report, "isError": report["status"] != "success"})
            finally:
                self.active = None

    def message(self, value):
        if type(value) is not dict or value.get("jsonrpc") != "2.0" or type(value.get("method")) is not str:
            raise Invalid("expected JSON-RPC request or notification")
        if set(value) - {"jsonrpc", "method", "id", "params"}:
            raise Invalid("unsupported JSON-RPC member")
        method, params = value["method"], value.get("params", {})
        if type(params) is not dict:
            if "id" in value:
                self.error(value["id"], -32602, "params must be an object")
            return
        if "_meta" in params:
            if type(params["_meta"]) is not dict:
                if "id" in value:
                    self.error(value["id"], -32602, "_meta must be an object")
                return
            params = {k: v for k, v in params.items() if k != "_meta"}
        if "id" not in value:
            if method == "notifications/initialized" and self.negotiated and not params:
                self.initialized = True
            elif method == "notifications/cancelled" and set(params) <= {"requestId", "reason"}:
                requested = params.get("requestId")
                if type(requested) not in (str, int) or ("reason" in params and type(params["reason"]) is not str):
                    return
                with self.state_lock:
                    if self.active and type(requested) is type(self.active[0]) and requested == self.active[0]:
                        self.active[1].set()
            return
        identity = value["id"]
        if type(identity) not in (str, int) or (type(identity) is str and len(identity) > 128) or (type(identity) is int and abs(identity) > 9007199254740991):
            raise Invalid("invalid request ID")
        key = (type(identity).__name__, identity)
        if key in self.ids or len(self.ids) >= MAX_IDS:
            self.error(identity, -32600, "duplicate ID or session request limit")
            return
        self.ids.add(key)
        if method == "initialize":
            if self.negotiated or set(params) - {"protocolVersion", "capabilities", "clientInfo"} or not all(k in params for k in ("protocolVersion", "capabilities", "clientInfo")):
                self.error(identity, -32602, "invalid initialize parameters or repeated initialization")
                return
            if type(params["protocolVersion"]) is not str or type(params["capabilities"]) is not dict or type(params["clientInfo"]) is not dict or any(type(params["clientInfo"].get(k)) is not str or not params["clientInfo"][k] or len(params["clientInfo"][k]) > 128 for k in ("name", "version")):
                self.error(identity, -32602, "invalid client metadata")
                return
            self.negotiated = True
            self.result(identity, {"protocolVersion": PROTOCOL, "capabilities": {"tools": {"listChanged": False}},
                                   "serverInfo": {"name": "beryl-local", "version": "0.1.0"},
                                   "instructions": "Use actual capability/admission context. Context never proves runtime success. Execution tools run code only when explicitly invoked. Promotion remains a separate CLI operation."})
        elif method == "ping" and not params:
            self.result(identity, {})
        elif not self.initialized:
            self.error(identity, -32002, "initialize and notifications/initialized required")
        elif method == "tools/list":
            if params:
                self.error(identity, -32602, "no cursor or list parameters are supported")
            else:
                self.result(identity, {"tools": TOOLS})
        elif method == "tools/call":
            if set(params) - {"name", "arguments"} or type(params.get("name")) is not str or params["name"] not in TOOL_BY_NAME:
                self.error(identity, -32602, "unknown tool or missing arguments")
                return
            params = {"name": params["name"], "arguments": params.get("arguments", {})}
            try:
                validate(params["arguments"], TOOL_BY_NAME[params["name"]]["inputSchema"])
            except Invalid as exc:
                self.error(identity, -32602, str(exc))
                return
            with self.state_lock:
                if self.active:
                    self.error(identity, -32001, "another operation owns this adapter; wait or cancel it")
                    return
                cancel = threading.Event()
                thread = threading.Thread(target=self.worker, args=(identity, params["name"], params["arguments"], cancel))
                self.active = (identity, cancel, thread)
                thread.start()
        else:
            self.error(identity, -32601, "method not supported")

    def serve(self):
        try:
            while True:
                raw = sys.stdin.buffer.readline(MAX_FRAME + 1)
                if not raw:
                    break
                if len(raw) > MAX_FRAME or not raw.endswith(b"\n"):
                    self.error(None, -32700, "frame limit exceeded or missing newline; closing transport")
                    break
                try:
                    value = decode(raw)
                except (ValueError, UnicodeError, RecursionError, TypeError) as exc:
                    self.error(None, -32700, str(exc))
                    continue
                try:
                    self.message(value)
                except (Invalid, TypeError) as exc:
                    self.error(None, -32600, str(exc))
        finally:
            with self.state_lock:
                active = self.active
                if active:
                    active[1].set()
            if active:
                active[2].join()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--workbench-tools", type=Path, help="trusted installed Workbench integration; required only for explicit mod verification")
    parser.add_argument("--timeout-seconds", type=float, default=120)
    args = parser.parse_args()
    if not math.isfinite(args.timeout_seconds) or not 0.05 <= args.timeout_seconds <= 1800:
        parser.error("timeout must be 0.05..1800 seconds")
    compiler, project = args.beryl.resolve(strict=True), args.project.resolve(strict=True)
    if not compiler.is_file() or not project.is_dir():
        parser.error("compiler file and project directory required")
    workbench = args.workbench_tools.resolve(strict=True) if args.workbench_tools else None
    if workbench and not workbench.is_dir():
        parser.error("workbench-tools must be an installed tool directory")
    Server(compiler, project, args.timeout_seconds, workbench).serve()


if __name__ == "__main__":
    main()
