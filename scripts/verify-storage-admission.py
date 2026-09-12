#!/usr/bin/env python3
"""Target copy/borrow containment and retained scalar List compatibility."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
# Exact in-script corpus: no glob can silently shrink the selected negatives.
CASES = (
    ("list_copy", "fn main(){var xs:List<i32>\nxs.push(1)\nvar ys=xs}", ("native", "enfusion")),
    ("list_replace", "fn main(){var xs:List<i32>\nvar ys:List<i32>\nxs=ys}", ("native", "enfusion")),
    ("record_copy", "struct S{xs:List<i32>}\nfn main(){var s=S{}\nvar b=s}", ("native",)),
    ("nested_copy", "struct S{xs:List<i32>}\nfn main(){var a=[S{}]\nvar b=a}", ("native", "enfusion")),
    ("owning_return", "struct S{xs:List<i32>}\nfn make()->S{return S{}}\nfn main(){}", ("native", "enfusion")),
    ("sink", "fn consume(sink xs:List<i32>){println(xs.len())}\nfn main(){var xs:List<i32>\nconsume(sink xs)}", ("native", "enfusion")),
    ("iteration", "fn main(){var xs:List<i32>\nxs.push(1)\nfor v in xs{xs.push(v)}}", ("native", "enfusion")),
    ("index_effect", "fn grow(inout xs:List<i32>)->i32{xs.push(9)\nreturn 0}\nfn main(){var xs:List<i32>\nfor i in 0..8{xs.push(i)}\nprintln(xs[grow(inout xs)])}", ("native", "enfusion")),
    ("argument_effect", "fn grow(inout xs:List<i32>)->i32{xs.push(9)\nreturn 0}\nfn read(let xs:List<i32>,n:i32)->i32{return xs.len()+n}\nfn main(){var xs:List<i32>\nprintln(read(xs,grow(inout xs)))}", ("native", "enfusion")),
    ("array_copy", "fn main(){var a=[1,2]\nvar b=a}", ("enfusion",)),
    ("reference_element", "struct R{x:i32}\nfn main(){var xs:List<R>\nxs.push(R{x:1})}", ("enfusion",)),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beryl", required=True, type=Path)
    parser.add_argument("--clang", required=True, type=Path)
    args = parser.parse_args()
    beryl, clang = args.beryl.resolve(), args.clang.resolve()
    work = Path(tempfile.mkdtemp(prefix="storage-admission-", dir=ROOT / "build"))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    tracked = [ROOT / p for p in ("src/sema/storage.c", "src/sema/storage.h", "tests/unit/test_storage_admission.c",
               "tests/e2e/lists.be", "tests/e2e/lists.expected", "examples/proof.be")]+[Path(__file__)]
    assert all(p.is_file() for p in tracked), "missing required source or expected-output fixture"
    hashes = lambda: {p.relative_to(ROOT).as_posix(): sha(p) for p in tracked}
    evidence = {"schema_version": 1, "status": "running", "compiler_sha256": sha(beryl),
                "input_hashes": hashes(), "commands": [], "expected_cases": [x[0] for x in CASES],
                "executed_cases": [], "rejected_commands": 0}
    env = os.environ.copy(); env["PATH"] = str(clang.parent)+os.pathsep+env.get("PATH", "")
    print(f"Artifacts: {work}", flush=True)

    def run(argv, expected=0):
        argv = list(map(str, argv))
        p = subprocess.run(argv, cwd=work, env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="strict", timeout=120)
        evidence["commands"].append({"argv": argv, "exit_code": p.returncode, "stdout": p.stdout, "stderr": p.stderr})
        if expected is not None and p.returncode != expected:
            raise AssertionError(f"unexpected exit {p.returncode}: {argv}\n{p.stdout}\n{p.stderr}")
        return p

    try:
        assert len(CASES) == 11 and len({x[0] for x in CASES}) == 11
        for name, body, targets in CASES:
            source = work / f"{name}.be"
            source.write_text(f'module storage_{name}\n{body}\ntest "not executed" {{ assert(true) }}\n', encoding="utf-8")
            prior = work / f"{name}-prior.exe"; prior.write_bytes(b"preserve previous executable")
            output = work / f"{name}-enfusion"; output.mkdir()
            sentinel = output / "prior.c"; sentinel.write_bytes(b"preserve prior generated source")
            for target in targets:
                if target == "native":
                    commands = [["check", source], ["check", "--format", "json", source], ["emit-c", "--tests", source],
                                ["build", "--clang", clang, "-o", prior, source], ["run", "--clang", clang, "-o", prior, source],
                                ["test", "--clang", clang, source], ["test", "--release", "--clang", clang, source]]
                    code = "BE0903"
                else:
                    commands = [["check", "-t", "enfusion", source], ["check", "-t", "enfusion", "--format", "json", source],
                                ["build", "-t", "enfusion", "--out-dir", output, source]]
                    code = "BE0701"
                for command in commands:
                    cache_before = set((work / ".beryl-cache").rglob("*"))
                    p = run([beryl, *command], expected=None)
                    assert p.returncode != 0 and code in p.stdout+p.stderr and "storage admission" in p.stdout+p.stderr, (command, p.stdout, p.stderr)
                    assert set((work / ".beryl-cache").rglob("*")) == cache_before, "rejected input started a job"
                    assert prior.read_bytes() == b"preserve previous executable"
                    assert sentinel.read_bytes() == b"preserve prior generated source" and list(output.iterdir()) == [sentinel]
                    if command[0] == "emit-c": assert not p.stdout, "rejected input emitted native C"
                    evidence["rejected_commands"] += 1
            evidence["executed_cases"].append(name)

        fixture = ROOT / "tests/e2e/lists.be"
        expected = (ROOT / "tests/e2e/lists.expected").read_text(encoding="utf-8").replace("\r\n", "\n")
        assert expected.strip(), "empty List output oracle"
        for release in ([], ["--release"]):
            p = run([beryl, "run", "--clang", clang, *release, "-o", work / ("lists-release.exe" if release else "lists-debug.exe"), fixture])
            assert p.stdout.replace("\r\n", "\n") == expected, "List output differs from preserved expected fixture"
        run([beryl, "check", "-t", "enfusion", fixture])
        generated = work / "lists-generated"; generated.mkdir()
        run([beryl, "build", "-t", "enfusion", "--out-dir", generated, fixture])
        assert any(generated.rglob("*.c")), "no Enfusion sources generated"
        capture = work / "scalar_capture.be"
        capture.write_text('module scalar_capture\nstruct Counter{value:i32}\n'
                           'fn Counter.next(inout self)->i32{self.value+=1\nreturn self.value}\n'
                           'fn grow(inout xs:List<i32>)->i32{xs.push(9)\nreturn 0}\n'
                           'fn read(value:i32,n:i32)->i32{return value+n}\n'
                           'fn main(){var c=Counter{value:1}\nprintln(min(c.value,c.next()))\n'
                           'var xs:List<i32>\nxs.push(1)\nprintln(read(xs[0],grow(inout xs)))}\n', encoding="utf-8")
        for release in ([], ["--release"]):
            p = run([beryl, "run", "--clang", clang, *release, "-o", work / ("capture-release.exe" if release else "capture-debug.exe"), capture])
            assert p.stdout.replace("\r\n", "\n") == "1\n1\n", "scalar let capture ordering changed"
        run([beryl, "check", "-t", "enfusion", capture])
        proof = ROOT / "examples/proof.be"
        run([beryl, "check", proof]); run([beryl, "check", "-t", "enfusion", proof])
        evidence["legacy_list_expected_sha256"] = sha(ROOT / "tests/e2e/lists.expected")
        evidence["positive_scope"] = "native debug/release exact List and scalar-capture output; Enfusion List generation, scalar-capture and proof checks; no engine execution or cleanup proof"
        evidence["input_hashes_after"] = hashes()
        assert evidence["input_hashes_after"] == evidence["input_hashes"] and sha(beryl) == evidence["compiler_sha256"], "inputs changed"
        assert evidence["executed_cases"] == evidence["expected_cases"]
        evidence["status"] = "success"
    except Exception as exc:
        evidence["status"] = "failure"; evidence["failure"] = str(exc)
        raise
    finally:
        (work / "results.json").write_text(json.dumps(evidence, indent=2)+"\n", encoding="utf-8")
    print(f"passed {len(CASES)} cases / {evidence['rejected_commands']} rejected commands plus retained List compatibility", flush=True)


if __name__ == "__main__":
    main()
