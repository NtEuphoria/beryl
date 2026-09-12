# SPARKOS implementation state

Updated: 2026-09-07. This is the durable execution record for the
[approved implementation plan](SPARKOS_IMPLEMENTATION_PLAN.md).

## Goal

Deliver Beryl as a dependable, local, model-neutral Enfusion authoring system.
The first release replaces the complete current MESH PID with verified generated
code. Subsequent releases grow into components, whole mods, and measured optimization.

## Success criteria

Each milestone must pass its own gates in the approved plan. Code generation,
native execution, Workbench compilation, host gameplay, independent multiplayer,
and visual inspection are different evidence levels. No absent result is success.

## Status

Implementation remains authorized. M3's isolated-candidate gate passed on
2026-09-07 in `build/mesh-pid-ej8h72g_`. The first release's defined candidate
acceptance gate is complete: the full Beryl PID ran in MESH through the existing
gameplay suite and actual control handover. M4–M8 and independent multiplayer
remain incomplete. The live MESH project has not been migrated.

## Current step

The approved [advanced program](BERYL_ADVANCED_IMPLEMENTATION_PLAN.md) now refines
the M4–M8 sequence. Its [execution state](BERYL_ADVANCED_IMPLEMENTATION_STATE.md)
records the Stage A/B foundation, isolated Stage C fixtures and experimental
scalar Stage D implementation. Later gates remain open.

M4: dependable engine context, source mappings and reusable validation. The
recorded integer-binding concerns have been reproduced and repaired, with exact
engine evidence in the advanced execution state. Broader binding contracts,
remaining scenarios and complete AI usability acceptance are still open.
The M3 full PID port, constructor exports and initial companion workflow are
implemented, installed and verified in the isolated MESH candidate.
M2's bounded Windows reference/native gate passed; see M2_IMPLEMENTATION.md.
M1's module/naming/scalar-export gate has passed on Windows and Workbench.
M0's ordinary-command gate has passed on Windows; POSIX execution and broader
malformed-input hardening remain explicitly unverified/open in its packet.

## Completed

- Reviewed the compiler, existing roadmap and research, actual MESH PID/store,
  Workbench tools, SPARKOS brand rules, and current working-tree changes.
- Previous correctness work is recorded in FOUNDATION_IMPLEMENTATION.md.
- Existing default compiler passed the foundation suite before this turn:
  build/foundation-xw1faoiu/results.json (259 cases, 1,104 checks; 13 native
  O0/O2 regression programs; existing PID examples). This is baseline evidence,
  not evidence for the new implementation.
- Approved plan consolidated into docs; preexisting modifications will be preserved.
- Baseline hashes: build/baseline-414eec4e78e84007ab296546d0d58e3e/baseline.json.
- First M0 foundation run: build/foundation-lqth7zk9/results.json passed 269 cases /
  1,155 checks, all 13 O0/O2 regressions, and existing PID tests. New unit cases
  execute real subprocesses for argument delivery, independent output channels,
  exit 127, missing executables, timeout, and capture failures.
- Full CLI driver gates passed in build/driver-o0gspfjp/results.json: JSON/errors,
  manifest policy, real run/test, failed builds/publication preserving prior output,
  lying compiler, exit 127, six concurrent jobs, contended output lock, runtime
  timeout, externally signalled cancellation, and non-overwriting package creation.
  Subsequent identity/UTF-8 refinements require a fresh final validation pass.
- Sanitized foundation run build/foundation-ckqfsl40/results.json passed 270 cases /
  1,158 checks and the complete prior regression set. Its compiler also passed
  build/driver & spaces-bdzhcxvo/results.json, including source/executable SHA-256
  checks, malformed UTF-8 diagnostics, and a working directory with metacharacters.
- Engine/tool baseline: build/baseline-414eec4e78e84007ab296546d0d58e3e/engine.json.
  Installed Workbench is 1.8.0.13, SHA-256
  7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798.
  Integration HEAD 51e9ca0306a4ebff66ae2e42e9decba087f0c07b has preexisting dirty
  files; script hashes are captured separately.
- Release foundation build/foundation-s2ke_95t/results.json passed with source
  stability checks; build/driver & spaces-ha_fncu_/results.json passed including
  PATH/compiler-shadowing regression. Updated shell check-all passed 270 cases /
  1,158 checks, 13 e2e programs, PID examples, and 66 diagnostic codes.
- Final flag review retained the previous debug symbols/release unwind options
  while disabling FP contraction/fast-math for parity. Revalidating this exact
  final M0 source before recording the module-work checkpoint.
- Final M0 validation passed: build/foundation-w9zkgi93/results.json (270 cases /
  1,158 checks; 13 O0/O2 programs; existing PID tests), plus
  build/driver & spaces-h0bhwviq/results.json (all CLI gate groups).
- Exact validated compiler installed at build/beryl.exe, SHA-256
  7dd9d30702b6c7637d31d4c833903345651c25e53116dbb7555118c02f3413ca.
  Publication and rollback record: build/foundation-w9zkgi93/publication.json.
  The pre-turn compiler is preserved in build/foundation-s2ke_95t/previous-default-beryl.exe.

## Active owners

Codex in this task, with three bounded agents for native verification, engine
integer fixtures, and context tooling. One integrator owns shared CLI changes and
publication; the engine agent owns the current isolated Workbench sessions.

## Blockers

No current session blocker. The owned Workbench and game sessions exited after
verification. Independent multiplayer clients remain unverified.

## Next action

Follow the M4 packet. Preserve the successful M3 candidate and its rollback
fixture. Re-run PID/MESH verification when relevant source or compiler changes;
do not reuse evidence as proof of changed bytes. The full M3 gate need not be
repeated solely because the game was closed or the conversation resumed.

Historical M1 checkpoint (superseded by the installed M3 compiler below):
M1 final foundation: build/foundation-vblu_i1j/results.json, 295 cases / 1,235
checks; 15 native O0/O2 programs; shared PID tests; deterministic export output.
UBSan: build/foundation-tg0wxlnk/results.json, same complete corpus passed.
CLI: build/driver & spaces-e8x7l2cd/results.json, all gate groups passed.
Workbench: build/enfusion-proof-28cd13808d98483ba0792769a435511f/result.json,
exported multi-module ordinary bodies compiled, exit 0, no warnings/errors.
The exact M1 compiler was installed at build/beryl.exe, SHA-256
c9b5fb853096d5510bc74e779a7d1209af600c9e604ff5a6ceaf14f342c3d86e.
Publication and previous M0 compiler: build/foundation-vblu_i1j/publication.json
and previous-default-beryl.exe. Constructor mappings and complete PID remain M3.

## Next checkpoint

M4's compiler context and verified binding contracts, followed by generated-source
mapping and reusable validation. Its completion requires the packet's positive
and negative gates; M3 success alone does not close M4.

## Notes

- M4–M8 remain open. M0's Windows command gate and M1's tested declaration/export
  contract passed; constructor/companion orchestration is implemented. M0's documented platform
  and resource-hardening limits are not claimed complete.
- Native shell execution and content-changing retries are removed. Windows CLI
  concurrency, cancellation, and publication regression gates passed in the
  final M0 evidence above and retained by M1–M3.
- Preserve original MESH scripts and dirty terrain/tablet work. Use isolated
  candidates before integration, with hash-checked promotion and rollback.
- No claimed Rust speedup. Performance work begins after semantic validation.

## M2 checkpoint

Historical M2 installed SHA-256: 77b37cb58d2aa35dec024257bb30d55089ade0d1187fc648b3c8c32ac9e92315.
Normal foundation: build/foundation-3bys9qw6/results.json (309 cases / 1,820 checks).
UBSan: build/foundation-qbhjsxdh/results.json. Reference/differential including
three compiled mutations: build/reference-nj1ndyej/results.json. CLI:
build/driver & spaces-1zud1uax/results.json. Workbench precision compilation:
build/enfusion-proof-f6378159ca1e4bb6899f3f42209edd0a/result.json.
Publication and M1 rollback: build/foundation-3bys9qw6/publication.json and
previous-default-beryl.exe. Native remains default. Engine numerical execution,
full PID, generic ownership and POSIX execution are not implied by this gate.

## M3 implementation history (superseded by completion below)

- Full controller at packages/sparkos/pid/pid.be, plus shared native/reference tests.
- Constructor facade preserves one-object state and ordinary Beryl value construction.
- Strict initial companion schema, local check/build/compile verification, owned
  promotion and the versioned installed tool bundle have passed their recorded gates.
- Engine comparison build/pid-uti04hu2/result.json passed 2,186 complete operations,
  65,580 comparisons against original/generated/reference state; maximum reported
  difference was zero. A fresh hidden Workbench session loaded BerylPidComparison,
  returned its compiled source token, and only that owned session was stopped.
- Inverted-clamp branch cases were added and passed the final PID gate. Original fixture SHA:
  f03f8588b9c4c4298db1e933b4aafab5e778725faf30b4c734e23aa2b1bb2460.
- MESH candidate compilation and nine existing suites passed. Host runtime
  acceptance did not execute because of the existing game session.

Latest M3 progress: build/pid-v1pygjvv/result.json passed 2,195 operations / 65,850
engine field comparisons, maximum difference zero, including inverted-clamp cases.
build/mesh-pid-h9typfpz compiled and passed all nine selected existing MESH suites.
Gameplay was refused before launch because of the existing game; actual handover
remains unexecuted. See M3_IMPLEMENTATION.md. Final normal compiler validation:
build/foundation-d3l4o2d4/results.json (310 cases / 1,831 checks). Other final gates
and versioned tool installation tests passed against that candidate.

M3 compiler installed: c7a7b3b10221b74f9078aeded70206f34f2c76d9b4242f8d0bea6455dac31f85.
Tool bundle: 73d0ab5bb1ffb3bd2afed2bf8486be1a86fe092f9c7768e7d03b0078315eeaef.
Final UBSan foundation: build/foundation-2jiejps6/results.json; driver:
build/driver & spaces-1eug_bvr/results.json; reference:
build/reference-gpv8opmd/results.json; mod tools:
build/mod & spaces-qfus7jw3/result.json; full PID engine comparison:
build/pid-i8zji6j2/result.json. Publication/rollback:
build/foundation-d3l4o2d4/publication.json and previous-default-beryl.exe.
M3 remains open at host gameplay/handover. M4 preparatory inspection can proceed;
do not mark the first release complete because the compiler/tool gates passed.

Installed-command end-to-end evidence: `build/installed-pid-build.json`,
`build/installed-pid-compile.json`, `build/installed-pid-promote.json`. Artifact
`d371f54b370a4084a8ba050855275606` was compiled in Workbench then promoted into the
compiler-owned `build/validated-addons/BerylSparkosPid` directory. This exercised
the default installed Python/tool lookup without development environment overrides.
The bundle and old compiler versions remain available for rollback.

Preservation check after staging/testing: all 221 files in the original MESH
snapshot still match `build/mesh-pid-h9typfpz/mesh-baseline.json`. No live MESH
source or brandkit file was edited. Existing Beryl working-tree edits are retained.
The earlier game-closing question was answered on 2026-09-07.

## M3 candidate gate completed — 2026-09-07

`build/mesh-pid-ej8h72g_/result.json` reports success with the exact installed
compiler and unchanged PID comparison inputs. Workbench compilation and all nine
selected existing suites passed. The actual game executed all 18 expected
acceptance checks, with zero failures/skips and its DONE marker. The compiled-token
handover fixture passed exactly once: both manual takeover and release cleared
all three PID controllers and saturation, preserved configuration, and retained
the same three controller objects. No generated PID code was manually corrected.

- MESH source fingerprint: `742da27de4e5311a63ab586587117944da9efe1b0afa31a87fc797cb6ceb91fa`.
- Staged artifact fingerprint: `0437bfbc72be73524990c757c0f7a5f191aea6695c8a7b330bbd695f8f6d08b0`.
- Compiled token: `9e0681941116bbdcdf80099becbd90b8534909ea0f91d5fcfc6108da8f263022`.
- Raw gameplay evidence: `build/mesh-pid-ej8h72g_/game-console.log`.
- Candidate and original inventories remained consistent through validation;
  the permitted engine-written resource database is excluded from candidate
  immutability checks. The complete original MESH inventory remained unchanged.
- Post-run process inspection found no remaining game or Workbench session.

This closes the plan's first release **in a verified isolated MESH candidate**.
Live-project migration, visual inspection and dedicated two-client acceptance
have not been performed. No native performance comparison is implied.
