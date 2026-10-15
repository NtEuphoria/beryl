# Harmless WorkbenchGameCommon dispatch experiment

This trusted isolated addon tests the documented zero-argument
`thread Beryl_RunSentinel();` and `Sleep(200)` syntax. It never opens an editor
module or resource, loads a world, spawns an entity, calls UI services, or invokes
a generated component. It needs no Beryl compiler.

The fixed NetApiHandler and global worker are staged together under
`scripts/WorkbenchGameCommon/`. They share one compiled token and bounded static
phase/counters. Arm is submitted once. Status never rearms. A lost module state,
duplicate worker or incomplete response fails the experiment.

The first arm response must report zero resumed executions. A later status
response must report exactly one entered and one resumed execution, and the
complete four-event sequence. This establishes separate native snapshots; it
does not infer network transmission order from source order or establish
Workbench-only lifetime, native resource-opening safety, world readiness, or
engine callback delivery. The Workbench module getter is informational; the
Game module getter and exact compiled handler token are checked independently.

Preparation is the default:

```text
python scripts/verify-workbench-dispatch.py --workbench-tools <installed-plugin>
python scripts/verify-workbench-dispatch.py --self-test
```

Only the engine owner may request the explicit run:

```text
python scripts/verify-workbench-dispatch.py --run --workbench-tools <installed-plugin> --powershell-host <configured-pwsh> --engine-exe <installed-workbench> --engine-version <exact-file-version>
```

The preparer freezes exact source/tool/host/engine inputs and addon files, retains
raw compile/runtime receipts and logs, and rechecks identities before and after
operations. The runtime adapter uses existing plugin transports and the shared
ownership mutex. It refuses an existing/reused session, polls within fixed
bounds, and confirms exit of only its exact owned process. No policy flags,
installation, source promotion, guessed startup flags or editor execution occurs
in default preparation or synthetic receipt tests.

See `docs/advanced/P4_WORKBENCH_DISPATCH_DIAGNOSIS.md` for the primary API
inventory and the separately proposed Workbench-only/reflected alternatives.

The exact frozen direct-thread candidate ran successfully on engine 1.8.0.13:
`build/workbench dispatch & spaces-csb3u27_/result.json`. Script compilation was
clean and all six installed dispatch cases completed. Its arm snapshot recorded
entered=1/resumed=0; the subsequent status recorded entered=1/resumed=1. Ordered
stamps were arm=1, entered=2, caller after-thread/submitted=3, resumed=4. Both
raw snapshots and logs are retained; owned process exit was confirmed. The
receipt SHA-256 is
`f1e0c1251497ba4c06ccdba0bd8a0cd85fd4d26b6825d1c0e1b935d1cdc06880`.
This is evidence for these compiled bytes and the harmless GameCommon worker,
not for any native opener or callback experiment. No Beryl compiler was used.
