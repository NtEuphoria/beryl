# P4: actual world-save eligibility observation

Checkpoint: October 10, 2026. This extends the
[startup diagnosis](P4_WORLD_STARTUP_DIAGNOSIS.md). The experiment compiled and
executed, but its proposed serializer capability is **unavailable in the tested
Workbench configuration**. Serialization and the seven component callback cases
remain unrun.

## Result and its limits

The fresh owned Workbench 1.8.0.13 session exposed a game context and an unnamed
Workbench edit world. `Game.GetWorldEditor()` returned null. The handler therefore
had no game-editor API or world to compare against the Workbench objects. It
returned an explicit unavailable observation rather than invoking `SaveWorldAs`.

| Actual observation | Result |
|---|---|
| Game context | Present |
| Game play mode | False |
| WorldEditor module, API and world | Present |
| Workbench edit mode / game mode | True / false |
| Workbench world path | Empty |
| Game editor, API and world | Absent |
| API/world reference equality | Not established; both flags false |
| Future output file and its parent | Remained absent |
| Serialization, reload, play, spawn, component callbacks | Not run |

This is a target/session capability limitation, not proof of a Beryl logic bug,
an invalid world format, or the cause of the historical PowerShell stall. It does
not prove the serializer is unavailable in every game/editor configuration.
Native equality expressions compiled, but runtime equality could not be tested
because the required game-editor handles were absent.

The runtime used exactly six arguments: `-gproj`, the owned addon path,
`-noOpenLastResource`, `-scriptAuthorizeAll`, `-wbmodule=WorldEditor`, and `-run`.
There was no resource opener or load argument. Exactly three actual RPCs ran:
`IsWorkbenchRunning`, `GetLoadedProjects`, and `BerylWorldSaveEligibility` with
the installed token and action `observe`.

The owned engine process was stopped with confirmed identity and exit. The
runtime receipt records 21,952 milliseconds, 14 listener observations, 21 process
identity checks, no cleanup errors, and no evidence errors. Both enclosing
PowerShell processes also confirmed exit. The runtime's exit code 1 represents
its documented unavailable outcome; it is not a timeout or a matching source
trap.

## Immutable evidence

| Evidence | Receipt | Scope |
|---|---|---|
| Pure PowerShell checker gate | [a34f checker receipt](../../build/world-save-checkers-a34f00752f1b451a89713f4a770cdc56/outer/result.json) | 164 actual checker cases; extracted functions only, no engine |
| Independent receipt faults | [fj5 envelope receipt](../../build/world-save-receipts-fj5ssmch/result.json) | 140 inert cases; no PowerShell/compiler/engine |
| Actual isolated experiment | [fjw results](<../../build/world eligibility & spaces-fjw7shsx/results.json>) | Preserved staging, clean engine compilation, complete unavailable observation |
| Raw compile result | [fjw compile](<../../build/world eligibility & spaces-fjw7shsx/engine-compile.json>) | Exact engine script compilation |
| Raw runtime result | [fjw runtime](<../../build/world eligibility & spaces-fjw7shsx/engine-runtime.json>) | Raw/normalized RPCs, process ownership, input identities and retained engine logs |
| Independent actual-receipt audit | [serializer audit](../../build/oct10-world-save-runtime-audit-2036f94c44af42efb7db21dc00264ebf.json) | Rehashed retained inputs and logs; equality expressions did not execute with absent handles |

Actual result SHA-256:
`3f5a8d5a0f27337da415e7b295f3629190133bb4044a9c0249d7658477bd7428`.
Runtime receipt SHA-256:
`f865fa7eb586db67ee616a26d254181aaab938994f065585170c0334cb346965`.
Compiler input was the already captured private compiler; it was not executed
again for this experiment. Workbench compiled the copied generated EnforceScript
and new observer. The original eight staged files remained intact; the only new
source was the ninth read-only handler. The sole admitted derived file was the
644-byte root `resourceDatabase.rdb`, separately hashed as noninput output.

## Implementation and repaired verification defects

The experimental interfaces are
[verify-world-save.py](../../scripts/verify-world-save.py),
[world-save-engine.ps1](../../scripts/world-save-engine.ps1), and the
[trusted handler](../../packages/sparkos/workbench-world-save/rpc.c.in).
They do not add a public save command or a released companion capability.

The Python driver validates the selected prepare-only receipt and retained
original artifact, copies their exact files, pins installed primary declarations
and integration tools, and preserves raw evidence. Its future output path is
fixed, short, ASCII, unlinked, absent and inside the new isolated addon. That
output namespace must remain absent throughout this observation-only phase.

Source review and deliberate fault fixtures caught and repaired these new-driver
defects before actual engine execution:

- A mismatch between the Python derived-file key `relative_path` and the
  PowerShell wire key `relative`.
- Scalar malformed records reaching `.get` before type validation.
- Numeric floats being accepted as boundary process IDs/start ticks.
- Boolean/integer equality admitting altered manifest, codec, and mirrored
  transport identities. These links now compare canonical typed JSON.
- Adapter outcome refinement potentially overriding an independent stale,
  cancelled or timeout result. Primary failures now remain primary.

The receipt-test generator also had an aliasing defect: mutating its candidate
tool table mutated the expected table. That failed draft is retained at
`build/world-save-receipts-yjkq86nu/result.json`. The next draft retained four
canonical-linkage failures and source drift at
`build/world-save-receipts-lf9qkscb/result.json`. The final frozen gate passed all
140 cases with unchanged sources. Earlier failures were not rewritten as passes.

The frozen driver is `0547964fa68d0c1b58fd245ec3cbd5ebf612e789ff9619548fc96c632e5c92dc`;
the adapter is `bc15fad65faa208723bf7764e0df0cc6531418ed663d8d93afe1eb39d09ccd01`.
Receipts apply only to these identities and their explicit coverage.

## Next boundary

Do not call `SaveWorldAs` on a fabricated/detached editor, substitute parameterless
`Save`, overwrite the captured world, or weaken the identity gate to make this
route pass. The available API declarations alone do not establish an alternate
serializer contract.

The subsequent [layered-world investigation](P4_LAYERED_WORLD_DIAGNOSIS.md)
inspected installed world resources and the shipped `SCR_WorldFilesHelper`.
`EmptyEden` contains terrain and environmental-system tokens in its retained
compiled payload; it was not selected as an established minimal fixture. The
helper supplies a two-file default world template, now staged in a separately
identified source-backed experiment. The helper was not invoked, so this does
not close engine-authored serialization. Native loading remains a separate gate.

Any admitted next loading profile must use a new isolated artifact and receipt,
retain its exact source/dependency identity, perform one explicit mechanism, and
prove the observed native world path before play or spawn. Preserve the existing
seven callback cases and their actual engine-delivery requirements. Host-only
success, handwritten callback invocation, and accepted `Opened` alone do not
close this gate.
