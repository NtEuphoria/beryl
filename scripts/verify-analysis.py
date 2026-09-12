#!/usr/bin/env python3
"""Bounded, isolated checks of the exact-snapshot C analyzer; no engine/build jobs.

All authored inputs and raw observations are retained under an owned build dir.
This is a test harness only. Ordinary analysis does not require Python.
"""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree(path: Path) -> dict[str, str]:
    return {str(p.relative_to(path)): sha(p.read_bytes()) for p in path.rglob("*") if p.is_file() and not p.is_symlink()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--standalone", action="store_true", help="private analyzer harness; omit for normal beryl")
    parser.add_argument("--work-root", type=Path, default=Path("build"))
    args = parser.parse_args()
    executable = args.beryl.resolve(strict=True)
    args.work_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="analysis & spaces-", dir=args.work_root.resolve()))
    command = [str(executable)] + ([] if args.standalone else ["analyze"])
    records: list[dict] = []
    results = {"schema_version": 1, "operation": "verify-analysis", "compiler": str(executable),
               "compiler_sha256": sha(executable.read_bytes()), "work_directory": str(work),
               "groups": records, "status": "running", "platform": os.name,
               "limitations": ["bounded deterministic malformed-input corpus, not exhaustive fuzzing",
                               "filesystem ownership/ACL verification unavailable",
                               "POSIX race behavior requires a POSIX run", "no program or engine execution"]}
    sequence = 0
    source = b"module demo\nfn main() { let x = 1 + 2 }\n"

    def make_request(data: bytes = source, **fields) -> dict:
        result = {"schema_version": 1, "request_id": "snapshot.1", "snapshot_version": 20,
                  "target": "native", "forbid_unsafe": True,
                  "expected_compiler_sha256": results["compiler_sha256"],
                  "sources": [{"path": "src/main.be", "sha256": sha(data), "document_version": 9, "content_file": "0001.be"}]}
        result.update(fields)
        return result

    def run(name: str, request: dict | bytes, expected: tuple[int, str], *, content: bytes | None = source,
            setup=None, stage: str | None = None, check=None) -> dict:
        nonlocal sequence
        sequence += 1
        case = work / f"{sequence:03d}-{name}"
        case.mkdir()
        raw = request if isinstance(request, bytes) else json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        (case / "request.json").write_bytes(raw)
        if content is not None:
            (case / "0001.be").write_bytes(content)
        if setup:
            setup(case)
        before = tree(case)
        environment = os.environ.copy()
        environment["BERYL_CLANG"] = str(case / "missing clang.exe")
        environment["BERYL_PYTHON"] = str(case / "missing python.exe")
        started = time.monotonic()
        completed = subprocess.run(command + ["--request", str(case / "request.json")], cwd=case,
                                   env=environment, capture_output=True, timeout=30)
        (work / f"{sequence:03d}.stdout.json").write_bytes(completed.stdout)
        (work / f"{sequence:03d}.stderr.txt").write_bytes(completed.stderr)
        observed = json.loads(completed.stdout)
        assert (completed.returncode, observed["status"]) == expected, (name, completed.returncode, observed)
        assert not completed.stderr, (name, completed.stderr)
        assert observed["operation"] == "analyze" and observed["schema_version"] == 1
        assert observed["execution"] == "not_run" and observed["engine_verification"] == "not_run"
        assert observed["request_fingerprint"] == sha(raw), (name, "wrong request fingerprint")
        assert tree(case) == before, (name, "analysis mutated fixture")
        if stage:
            assert observed["stage"] == stage, (name, observed)
        if check:
            check(observed)
        records.append({"case": name, "status": "success", "expected_exit": expected[0],
                        "expected_status": expected[1], "stage": observed["stage"],
                        "request_sha256": sha(raw), "elapsed_seconds": time.monotonic() - started,
                        "stdout": f"{sequence:03d}.stdout.json", "stderr": f"{sequence:03d}.stderr.txt"})
        return observed

    try:
        good = run("exact-native", make_request(), (0, "success"))
        assert good["sources"][0] == {"path": "src/main.be", "sha256": sha(source), "document_version": 9, "file_id": 0}
        for target in ("reference", "enfusion"):
            run("target-" + target, make_request(target=target), (0, "success"))
        changed = make_request(snapshot_version=21)
        changed["sources"][0]["document_version"] = 10
        newer = run("versions", changed, (0, "success"))
        assert newer["snapshot_fingerprint"] != good["snapshot_fingerprint"] and newer["source_fingerprint"] == good["source_fingerprint"]
        raw = json.dumps(make_request(), separators=(",", ":")).encode()
        for name, raw_bad in [("duplicate", raw[:-1] + b',"target":"reference"}'),
                              ("escaped-duplicate", raw[:-1] + b',"\\u0074arget":"reference"}'),
                              ("bom", b"\xef\xbb\xbf" + raw),
                              ("utf8", raw.replace(b"snapshot.1", b"\xc0\xaf")),
                              ("high-surrogate", raw.replace(b"snapshot.1", b"\\ud800")),
                              ("low-surrogate", raw.replace(b"snapshot.1", b"\\udc00")),
                              ("trailing", raw + b" true"),
                              ("deep", b"[" * 49 + b"0" + b"]" * 49)]:
            run(name, raw_bad, (1, "failure"), stage="request_parse")
        for name, modify in [
            ("unknown-root", lambda q: q.update(shell="forbidden")),
            ("unknown-source", lambda q: q["sources"][0].update(code="forbidden")),
            ("version-two", lambda q: q.update(schema_version=2)),
            ("no-policy", lambda q: q.pop("forbid_unsafe")),
            ("string-bool", lambda q: q.update(forbid_unsafe="false")),
            ("bad-target", lambda q: q.update(target="llvm")),
            ("float-version", lambda q: q.update(snapshot_version=1.0)),
            ("negative-version", lambda q: q.update(snapshot_version=-1)),
            ("large-version", lambda q: q.update(snapshot_version=9007199254740992)),
            ("empty-selection", lambda q: q.update(sources=[])),
            ("nul-id", lambda q: q.update(request_id="a\0b")),
            ("bad-hash", lambda q: q["sources"][0].update(sha256="A" * 64)),
        ]:
            q = make_request(); modify(q)
            run(name, q, (1, "failure"), stage="request_schema")
        for i, path in enumerate(["../outside.be", "/absolute.be", "C:/absolute.be", "\\\\server\\file.be", "src\\main.be",
                                  "src//main.be", "src/./main.be", "src/../main.be", "src/main.be:ads", "src/bad . /main.be"]):
            q = make_request(); q["sources"][0]["path"] = path
            run(f"logical-path-{i}", q, (1, "failure"), stage="request_schema")
        for i, path in enumerate(["../0001.be", "/0001.be", "C:/0001.be", "\\\\server\\file", "\\\\.\\NUL", "CON", "NUL.txt", "LPT1.be", "COM9.x", "0001.be:ads", "dir/0001.be"]):
            q = make_request(); q["sources"][0]["content_file"] = path
            run(f"content-path-{i}", q, (1, "failure"), stage="request_schema")
        q = make_request(); q["sources"].append({**q["sources"][0], "path": "SRC/MAIN.be", "content_file": "0002.be"})
        run("duplicate-logical", q, (1, "failure"), stage="request_schema")
        q = make_request(); q["sources"].append({**q["sources"][0], "path": "src/other.be", "content_file": "0001.BE"})
        run("duplicate-content", q, (1, "failure"), stage="request_schema")
        q = make_request(); q["sources"] = [{**q["sources"][0], "path": f"src/file{i}.be", "content_file": f"file{i}.be"} for i in range(65)]
        run("source-count-limit", q, (1, "failure"), stage="request_schema")

        def logical_disk(case: Path):
            (case / "src").mkdir(); (case / "src/main.be").write_bytes(source)
        run("missing-overlay-no-fallback", make_request(), (1, "failure"), content=None, setup=logical_disk, stage="source_read")
        run("hash-mismatch", make_request(), (2, "stale_input"), content=source + b"// changed\n", stage="source_identity")
        run("compiler-mismatch", make_request(expected_compiler_sha256="0" * 64), (2, "stale_input"), stage="compiler_identity")
        for name, data in [("source-utf8", b"module demo\n\xff"), ("source-nul", b"module demo\n\0")]:
            run(name, make_request(data), (1, "failure"), content=data, stage="source_encoding")
        data = b"module demo\r\n// \xce\xbb overlay\r\nfn main() { let x = missing }\r\n"
        diagnostic = run("byte-spans", make_request(data), (1, "failure"), content=data, stage="type_check")
        location = diagnostic["diagnostics"][0]["primary"]
        assert location["offset"] == data.index(b"missing") and location["length"] == 7 and location["line"] == 3
        assert diagnostic["location_encoding"]["column_unit"] == "byte"
        data = b"module demo\n@untrusted\nfn input(i:i32)->i32{let a=[1,2]\nreturn a[i]}\n"
        taint = run("taint", make_request(data), (1, "failure"), content=data, stage="taint")
        assert any(d["code"] == "BE0601" for d in taint["diagnostics"])
        data = b"module demo\nfn main(){var xs:List<i32>\nxs.push(1)}\n"
        run("unsupported-reference", make_request(data, target="reference"), (3, "unavailable"), content=data, stage="target_admission")
        run("oversized-content", make_request(), (1, "failure"), content=b" " * (1048576 + 1), stage="source_read")
        aggregate_data = b"//" + b"x" * (1048576 - 2)
        q = make_request(aggregate_data)
        q["sources"] = [{"path": f"src/part{i}.be", "sha256": sha(aggregate_data), "document_version": i, "content_file": f"part{i}.be"} for i in range(9)]
        def aggregate_setup(case: Path):
            for i in range(9):
                (case / f"part{i}.be").write_bytes(aggregate_data)
        run("aggregate-byte-limit", q, (1, "failure"), content=None, setup=aggregate_setup, stage="source_read")
        token_data = b"module demo\n" + b";" * 262144
        run("aggregate-token-limit", make_request(token_data), (1, "failure"), content=token_data, stage="resource_limit")

        external = work / "external.be"; external.write_bytes(source)
        def hardlink(case: Path):
            os.link(external, case / "0001.be")
        run("hardlink-rejected", make_request(), (1, "failure"), content=None, setup=hardlink, stage="source_read")
        try:
            probe = work / "symlink-probe"; probe.symlink_to(external)
        except OSError as error:
            records.append({"case": "symlink-rejected", "status": "unavailable", "reason": str(error)})
        else:
            run("symlink-rejected", make_request(), (1, "failure"), content=None,
                setup=lambda case: (case / "0001.be").symlink_to(external), stage="source_read")

        # Independent files retain exact order and byte identity; no discovery.
        second = b"module helper\npub fn answer()->i32{return 42}\n"
        first = b"module demo\nuse helper.answer\nfn main(){let n=answer()}\n"
        q = make_request(first)
        q["sources"].append({"path": "src/helper.be", "sha256": sha(second), "document_version": 18, "content_file": "0002.be"})
        multi = run("complete-source-set", q, (0, "success"), content=first, setup=lambda case: (case / "0002.be").write_bytes(second))
        assert [s["document_version"] for s in multi["sources"]] == [9, 18]
        q["sources"].reverse()
        reverse = run("ordered-source-set", q, (0, "success"), content=first, setup=lambda case: (case / "0002.be").write_bytes(second))
        assert reverse["snapshot_fingerprint"] != multi["snapshot_fingerprint"]

        # Observe real held handles before racing/cancelling; no timing-only
        # assumption that a launched process has already consumed its input.
        if os.name == "nt":
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                          ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
            kernel.CreateFileW.restype = ctypes.c_void_p
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            bad_handle = ctypes.c_void_p(-1).value

            def write_locked(path: Path) -> bool:
                handle = kernel.CreateFileW(str(path), 0x40000000, 7, None, 3, 0, None)
                if handle != bad_handle:
                    kernel.CloseHandle(handle)
                    return False
                error = ctypes.get_last_error()
                assert error in (32, 33), ("unexpected file-open error", error)
                return True

            for cancel in (False, True):
                case = work / ("cancel-held-snapshot" if cancel else "held-snapshot")
                case.mkdir()
                data = b"module held\nfn main(){}\n" + b"".join(f"fn f{i}()->i32{{return {i}}}\n".encode() for i in range(1000))
                # Keep the exact held-input phase observable on fast compilers
                # without adding compiler hooks or assuming a sleep cancelled
                # anything. Eight admitted 1 MiB sources stay at the input cap;
                # padding is comments, so the semantic workload remains bounded.
                data += b"//" + b"x" * (1048576 - len(data) - 2)
                q = make_request(data)
                for i in range(1, 8):
                    prefix = f"module held_padding{i}\n//".encode()
                    padding = prefix + b"x" * (1048576 - len(prefix))
                    filename = f"padding{i}.be"
                    (case / filename).write_bytes(padding)
                    q["sources"].append({"path": f"src/{filename}", "sha256": sha(padding),
                                         "document_version": i, "content_file": filename})
                raw = json.dumps(q, separators=(",", ":")).encode()
                (case / "request.json").write_bytes(raw); (case / "0001.be").write_bytes(data)
                before = tree(case)
                proc = subprocess.Popen(command + ["--request", str(case / "request.json")], cwd=case,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
                observed_lock = False
                deadline = time.monotonic() + 10
                while proc.poll() is None and time.monotonic() < deadline:
                    if write_locked(case / "0001.be"):
                        observed_lock = True
                        assert write_locked(case / "request.json"), "manifest is not retained while source is held"
                        # Attempt a real write through Python as a second API.
                        try:
                            with (case / "0001.be").open("r+b") as stream:
                                stream.write(b"X")
                        except PermissionError:
                            pass
                        else:
                            raise AssertionError("writer was able to change held content")
                        if cancel:
                            proc.send_signal(signal.CTRL_BREAK_EVENT)
                        break
                    time.sleep(0.001)
                stdout, stderr = proc.communicate(timeout=30)
                (case / "observed.stdout.json").write_bytes(stdout)
                (case / "observed.stderr.txt").write_bytes(stderr)
                observed = json.loads(stdout)
                assert observed_lock, "did not establish a held-input observation; race test unavailable"
                assert not stderr, stderr
                assert (proc.returncode, observed["status"]) == ((2, "cancelled") if cancel else (0, "success")), observed
                assert observed["request_id"] == q["request_id"] and observed["request_fingerprint"] == sha(raw)
                after = tree(case)
                assert all(after[name] == digest for name, digest in before.items())
                records.append({"case": case.name, "status": "success", "observed_input_lock": True,
                                "expected_status": "cancelled" if cancel else "success",
                                "write_attempt": "blocked", "request_and_source_bytes": "unchanged"})
        else:
            records.append({"case": "POSIX-concurrent-input-change", "status": "unavailable",
                            "reason": "No deterministic read-phase synchronization fixture is installed on this platform yet."})
        results["status"] = "success"
    except BaseException as error:
        results["status"] = "failure"
        results["error"] = repr(error)
        raise
    finally:
        (work / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(work / "results.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
