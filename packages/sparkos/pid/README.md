# Beryl-authored SPARKOS PID

`pid.be` ports the complete current MESH controller. `pid_test.be` imports it;
`reference/SPK_PID.c.fixture` preserves the original bytes outside engine script
discovery. This package contains no Claude/OpenAI API call or model dependency.

## Authoring workflow for Claude, ChatGPT and humans

1. Read `pid.be`, its tests, `beryl.mod.json` and
   [the M3 packet](../../../docs/M3_IMPLEMENTATION.md).
2. Edit Beryl logic and the typed companion description. Keep the constructor
   and setter differences unless deliberately migrating the existing MESH API.
   `error` is a language keyword; use `err`. A generic intrinsic starting with
   a numeric literal needs the intended type, for example `max(0f32, tau)`.
3. Run the semantic check and then the explicit numerical tests from the Beryl
   repository root:

   ```text
   beryl mod check --project packages/sparkos/pid
   beryl test --backend differential --max-bytes 268435456 --clang <clang-path> packages/sparkos/pid/pid.be packages/sparkos/pid/pid_test.be
   ```

4. Generate an isolated candidate and use its returned artifact id:

   ```text
   beryl mod build --project packages/sparkos/pid
   beryl mod verify --project packages/sparkos/pid --artifact <id> --stage compile --workbench-tools <installed-plugin-directory>
   ```

5. For full PID or MESH changes, run `scripts/verify-pid.py` and
   `scripts/verify-mesh-pid.py` using their documented `--help` arguments.
   Inspect the result status, stage, counts and raw logs. Failed, incomplete,
   unavailable, cancelled, timed-out or stale results do not pass.
6. Promote only verified generated output into a compiler-owned addon directory:

   ```text
   beryl mod promote --project packages/sparkos/pid --artifact <id> --destination <generated-addon-directory>
   ```

   This command preserves handwritten files, checks previous generated hashes,
   and retains rollback evidence. It is not the MESH migration command: MESH's
   existing addon definition and handwritten PID are protected by its separate,
   hash-checked candidate migration. It does not claim gameplay validation.

No generated script needs a manual edit. Generated-source errors are repaired
in Beryl, the description, or the compiler and then rebuilt. Detailed statement
source maps and general engine binding lookup are still M4 work.

## Installed tooling

Ordinary Beryl compilation is C11 and does not need Python. The `mod` command
uses Python's standard library for local orchestration. Install the trusted tool
bundle beside the compiler:

```text
python tools/beryl-mod/install.py --compiler build/beryl.exe
```

Set `BERYL_PYTHON` to a Python executable if it is not on PATH. Development can
set `BERYL_MOD_TOOL` to the absolute trusted `tools/beryl-mod/mod.py`; a companion
description cannot select or supply a tool, shell command or build script.

The current schema covers addon identity, explicit sources, a declared engine
version and scalar class/constructor/method exports. Components, resource
definitions, prefab/layout generation and named runtime scenarios are not yet
admitted by this schema. Unknown fields fail instead of being ignored.

Workbench comparison has passed 2,195 operations and 65,850 field comparisons
against original/generated/reference execution, including inverted clamp
intervals. A separate MESH candidate compiled and passed nine selected existing
suites, all 18 host gameplay checks, and actual manual takeover/release resetting
all three controllers. The M3 packet records the exact September 7 evidence.
The live MESH project remains unchanged. These results do not establish native
performance, visual acceptance or dedicated-server correctness.
