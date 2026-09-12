# M3 implementation packet: complete MESH PID

Status: isolated MESH candidate gate passed on 2026-09-07. The live MESH project
has not been migrated. The generated standalone PID addon was separately promoted
into a compiler-owned build directory after its compile gate.
Governing plan: [SPARKOS_IMPLEMENTATION_PLAN.md](SPARKOS_IMPLEMENTATION_PLAN.md).

## Baseline and exact behavior

M0 Windows, M1 declaration/export and M2 bounded reference gates have passed.
Original controller: `SparkOS_Mesh/scripts/Game/SparkOSMesh/Flight/SPK_PID.c`,
SHA-256 `f03f8588b9c4c4298db1e933b4aafab5e778725faf30b4c734e23aa2b1bb2460`.
Retain exact bytes as a `.fixture` outside engine script discovery. The production
port is `packages/sparkos/pid/pid.be`; tests import this same module.

Preserve five constructor defaults, gain setters, negative constructor limit,
nonnegative setter limit, tau clamping, integral inspection, reset, nonpositive
timestep no-op, saturation-dependent integral freeze, clamping, derivative on
measurement and optional low-pass filtering. Disabling filtering retains the
filtered history; re-enabling resumes from it. Reset clears dynamic state but
keeps every configuration field. Setters do not reset dynamic state or clamp an
existing integral immediately. Field and arithmetic update order follow source.
An inverted clamp interval from a negative constructor limit needs explicit
engine comparison; do not assume the native and engine intrinsic agree there.

## Export representation

Add an explicit constructor mapping from an `inout self` initializer returning
void. Initial admission is scalar state and scalar read-only arguments with
literal defaults. Generate the Beryl value class with its plain default
constructor and an exported derived class with the original constructor.
The derived constructor invokes the same initializer on inherited state.
There is one object, no separately allocated state and no per-step allocation.
Value literals/copies use the plain base class, so exporting a constructor cannot
add initializer side effects to ordinary Beryl value construction or copying.
Public method names are inherited unchanged by the engine class. No extra hidden
constructor argument or mutable global construction flag is required.

`--export-constructor qualified.Type.initialize=EngineClass` is the compiler
interface consumed by the companion tool. It is validated alongside explicit
class/method mappings. Duplicate exports, wrong receivers/results/modes, reserved
names and unknown declarations fail before generation. A versioned JSON companion
will collect these mappings and explicit source sets, addon identity and binding
identity. Its fields contain data, not code or commands.

## Verification and rollout

1. Analytical finite fixtures use exact binary fractions for expected results.
2. Seeded stateful operations run through reference and native code, retaining
   every output and all nine persistent fields after each observed operation.
3. Original and generated EnforceScript execute together in an isolated addon.
   Rename the original class only in the comparison addon and append a read-only
   field observer; do not modify the saved original fixture. Compare every field and operation, including constructor
   limits, configuration changes, reset and nonpositive timesteps.
4. Compare finite float values using `max(1e-6, 1e-5 * max(abs(a), abs(b)))`;
   compare bools and transitions exactly. Investigate differences before changing
   code; do not widen tolerance to hide a failed port.
5. Stage a separate MESH copy from exact current source bytes. Preserve the user's
   terrain/tablet modifications. Replace only the PID source in that candidate,
   with exactly one production `SPK_PID`. Original fixture stays outside scripts.
6. Compile and run existing PID and relevant runtime acceptance, including reset
   and handover. Report host evidence separately from dedicated two-client work.

Each result includes source/compiler/binding/artifact identities, actual stage,
status, raw logs and counts. Promotion requires unchanged source and validated
artifact hashes and preserves rollback. Headless compilation cannot stand in
for a live NetAPI numerical run. Never reuse or stop an unrelated editor session.

## Current limitations

The small `examples/pid.be` remains a separate introductory example. This milestone
does not introduce IR, owning containers, store migration, networking, controller
retuning or optimization. Statement source maps, general context/binding discovery
and reusable runtime scenario dispatch remain M4 work. The initial companion
schema rejects component/resource/layout fields rather than pretending to support
the later whole-mod profile.

## Implementation history and evidence

- Full shared implementation and eight analytical/property tests are in
  `packages/sparkos/pid/`. After adding inverted-clamp branch cases, the suite
  executes 2,206 assertions. Native/reference output and state events agree.
- `build/pid-v1pygjvv/result.json`: 2,195 constructor/configuration/reset/get/step
  operations, including 1,024 seeded steps, compared in the reference, native and
  real Enfusion VM paths. Engine comparison executed 65,850 field/output checks;
  maximum reported difference was zero. The original/generated comparison and
  each implementation's reference comparison all ran. No tolerance was widened.
- `build/mod & spaces-8w6_5160/result.json`: companion schema failures, duplicate
  declarations/keys, missing inputs, deterministic isolated artifacts, unknown
  capabilities, stale sources/output, owned publication, locks and injected
  mid-publication rollback passed. Promotion policy tests explicitly use synthetic
  compile receipts; those tests do not constitute Workbench evidence.
- Real companion Workbench compilation:
  `packages/sparkos/pid/.beryl-mod/jobs/d1834abbe4fa48dbad111785df516db2/engine.json`.
  The full generated constructor/method interface compiled cleanly in 1.8.0.13.
- `build/mesh-pid-h9typfpz/`: isolated complete MESH candidate. One production
  `SPK_PID`, source snapshot/rollback, verification-only handover instrumentation
  and a candidate identity handler. Compilation and all nine selected existing
  Workbench suites passed (`engine-compile.json`, `engine-tests.json`).
- Its gameplay launcher refused an existing game process, PID 23984, created
  before this verification. No game acceptance or handover execution occurred.
  `result.json` correctly records failure at the host acceptance stage. The
  unrelated game was not stopped. The user has been asked to close it when ready.

The M3 compiler and versioned tools are now installed. Final normal and UBSan
evidence: `build/foundation-d3l4o2d4/results.json` and
`build/foundation-2jiejps6/results.json` (310 cases / 1,831 checks).
Driver: `build/driver & spaces-1eug_bvr/results.json`.
Reference: `build/reference-gpv8opmd/results.json`.
Companion and installed-bundle tests: `build/mod & spaces-qfus7jw3/result.json`.
Full PID comparison with this exact compiler: `build/pid-i8zji6j2/result.json`.
Installed compiler SHA-256:
`c7a7b3b10221b74f9078aeded70206f34f2c76d9b4242f8d0bea6455dac31f85`.
Tool bundle SHA-256:
`73d0ab5bb1ffb3bd2afed2bf8486be1a86fe092f9c7768e7d03b0078315eeaef`.
Publication and M2 rollback are under `build/foundation-d3l4o2d4/`.

The installed commands were also exercised without development tool/Python
environment overrides: `build/installed-pid-build.json`,
`build/installed-pid-compile.json`, `build/installed-pid-promote.json`.
The exact generated artifact was compiled and then promoted into
`build/validated-addons/BerylSparkosPid`, preserving an ownership manifest and
rollback record. All 221 original MESH snapshot files still matched after testing.

## Completed candidate gate — 2026-09-07

After the user closed the unrelated game, a fresh candidate was staged from the
current MESH source and verified against the installed compiler and exact PID
comparison proof. `build/mesh-pid-ej8h72g_/result.json` records success:

- Workbench 1.8.0.13 compilation passed.
- All nine selected suites passed: pid, flightspec, rotor, mixer, manual,
  guidance, task, loiter and datalink.
- All 18 existing host gameplay checks executed and passed, with no skips,
  duplicates or missing outcomes; the run reached its DONE marker.
- The actual flight controller's manual takeover and release paths cleared all
  three PID controllers and saturation, preserved configuration, and retained
  the same controller objects. The fixture passed exactly once with the staged
  compiled token.

The source snapshot, candidate inventory, raw logs, process output and original
PID rollback fixture are retained in that evidence directory. The generated
PID bytes still have SHA-256
`403dd5ef7a67efc670db2779bab2be81adbe9ce22bb4d98921f3d3c4d4a0b3e5`.
The MESH source fingerprint is
`742da27de4e5311a63ab586587117944da9efe1b0afa31a87fc797cb6ceb91fa`;
the staged candidate fingerprint is
`0437bfbc72be73524990c757c0f7a5f191aea6695c8a7b330bbd695f8f6d08b0`.
Raw gameplay evidence is `build/mesh-pid-ej8h72g_/game-console.log`.

All original MESH files remained unchanged. Only the isolated candidate contains
the generated replacement and verification instrumentation; no generated PID
file needed a manual correction. Both owned engine sessions exited and no game
or Workbench process remained in the post-run inspection.

The plan's first-release candidate criterion is now satisfied. This does not
claim live-project deployment, visual acceptance, or dedicated-server correctness
with independent clients. Those remain separate rollout and verification steps.
