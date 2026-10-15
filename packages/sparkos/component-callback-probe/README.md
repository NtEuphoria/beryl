# Experimental component callback fixture

The optional `--frame-diagnostics world-state-v1` adds one trusted read-only
handler. It samples at most twice during the live spawn phase: after the first
spawn reply and after the last bounded status poll. It records editor/game/owner
world equality, each world's frame number, owner ACTIVE flags and component FRAME
masks. It never changes the spawn world, flags, event mask, callbacks or seven
case acceptance rules. Owners are not dereferenced after deletion is requested.
The existing stage and overall deadlines include the extra RPC costs. These
observations are diagnostic instrumentation, not performance measurements or
proof of callback delivery. The default `off` profile stages no diagnostic
handler and sends no diagnostic RPC. Declaration provenance is retained in
`frame-state-contracts.json`; equality and scheduling remain runtime questions.

This package is a controlled runtime experiment, not a tablet port or a released
world-authoring template. Its generated component, observer, transport, native
world identity, authority and complete trace gates are described in
`docs/advanced/P4_COMPONENT_CALLBACK_DELIVERY.md`.

The current world tests a documented engine class as a standalone root:

```text
GenericWorldEntity {
}
```

The installed `interfaceGenericWorldEntity.html` declares this class and its
inheritance from GenericEntity. That proves the class exists; it does not prove
this serialized .ent root is valid. Standalone world admission, mode switching,
authority and callback delivery remain **unverified hypotheses**. Existing
world/prefab/addon paths and metadata identities are unchanged.

`fixtures/original-eden-world.ent.txt` retains the inherited Eden seed.
`fixtures/rejected-empty-subscene.ent.txt` retains the exact 13-byte rejected
empty SubScene candidate. Its gl3c63j7 attempt logged `Can't open Subscene` and a
62.1688 ms LoadWorld phase, then timed out at the first status RPC before spawn.
The inherited Eden attempt reached world and terrain loading before that same
RPC boundary timed out. These are different failures, not proof that terrain is
the general cause. All previous candidates and receipts remain preserved.

The new 19-input source-contract inventory keeps all preceding 18 inputs and
adds the exact installed GenericWorldEntity declaration. The earlier inventory
is retained in its existing immutable receipts.

The GenericWorldEntity attempt r1n7z589 logged the owned resource load and
CreateEntities, with LoadWorld at 69.5813 ms and no recorded world or VM error.
Its first status RPC still timed out before readiness was returned; no entity
was spawned and no callback was observed. This is not a released standalone
world template or proof of complete world initialization.

The last diagnostic candidate replaced only the resource-opening call with
the documented `Workbench.OpenResource(string filename) -> bool`. Its return
and eventual readiness remain target gates; no asynchronous or non-modal
behavior is assumed. `fixtures/previous-set-opened-resource-rpc.c.txt` retains
the exact preceding RPC template. The world, 19-input inventory, Python helper,
observer and transport remain unchanged.

At `build/component callbacks & spaces-it3wl_wr/results.json`, source generation
and engine compilation passed. The load request first returned pending; the
next status reply returned unavailable with `Owned world load request refused`.
The load stage took 461 ms. Native addon-path resolution still identified the
exact owned file, but no world-loading log, spawn or callback was recorded.
Owned process exit was confirmed. This diagnostic was not adopted as a working
world-opening route, and the callback gate remains open.

Further diagnosis would need evidence about owned editor-window readiness,
resource registration/path expectations, module routing or load completion.
Those are investigation hypotheses, not established causes or new source
settings. No additional execution or fallback is selected in this checkpoint.

## Current resource-identity experiment

The next fixed candidate separates native registration from file resolution.
It asks `Workbench.GetResourceName` for the independently pinned absolute file,
requires the exact metadata name `{BCCBA11B20261008}worlds/BerylCallbackProbe.ent`,
then independently resolves that name back to the same file. Only after both
observations succeed does it call `Workbench.OpenResource` once with that native
resource name. An empty name, a different name, a failed roundtrip or a refused
opening is unavailable; no alternate spelling is tried in the same job.

Each reply additionally reports actual module/API presence, the native resource
name and its absolute roundtrip. This makes a missing API distinguishable from
an initialized editor with no world. Presence is not a readiness guarantee.
The installed declarations document signatures, but supply no accepted-path
or synchronous-readiness promise. This remains an experiment, not a fix.

`fixtures/previous-absolute-open-resource-rpc.c.txt` preserves the exact preceding
RPC template (SHA-256 `ba32d6b0071ce6031fc245dd775e2cfb91992e1925db81837f41c35d018d3216`).
Its earlier receipts still describe only those earlier bytes. The world,
observer, authority and callback trace contracts are unchanged.

The first native-name trial, `build/component callbacks & spaces-zbkxr69s/results.json`,
compiled successfully. It observed the exact metadata resource name and an
existing WorldEditor module with a null API, but native `GetAbsolutePath` rejected
the complete GUID-based resource name. The admission gate returned unavailable
before any resource opening, world loading, spawn or callback. Owned process exit
was confirmed. Registration is now observed; the resolver spelling remains a
separate issue. This failed trial is preserved and is not counted as opening.

The current correction obtains the path through the documented
`ResourceName.GetPath()` accessor and records that raw path before native absolute
resolution. It still requires the exact metadata name and exact absolute file;
no guessed substring, alternative path or same-job retry is used. Its response
adds `resource_path`, and its contract inventory now includes the exact installed
ResourceName declaration (20 inputs). The previous GUID-roundtrip template is
preserved at `fixtures/previous-guid-roundtrip-rpc.c.txt`. Opening and eventual
readiness remain unverified until this corrected candidate executes.

At `build/component callbacks & spaces-6d_vvfs5/results.json`, the corrected
candidate compiled and the native path accessor returned
`worlds/BerylCallbackProbe.ent`. Its absolute roundtrip matched the owned file.
The global opener still returned false; no world or callback ran. The WorldEditor
module existed with a null API. Owned process exit was confirmed.

The next fixed candidate explicitly requests `Workbench.OpenModule(WorldEditor)`
once, even when the registered module object already exists. The old short-circuit
guard had skipped that request in this observed configuration. The new response
retains `module_open_requested` and the actual `module_open_accepted` Boolean.
Acceptance alone returns pending; actual API/world/mode/trace checks still gate
success. The global native-name opener remains unchanged, isolating this setup
correction. Refusal or timeout remains unavailable/incomplete, with no fallback.
`fixtures/previous-resource-path-opener-rpc.c.txt` retains the preceding exact
11,954-byte RPC (SHA-256 `0ff202eff2068a59927422a93d39420d8bc7a181bb843edcb55f3750a8f46c83`).

`build/component callbacks & spaces-spoin57k/results.json` confirms the explicit
module-open repair: the call was accepted, API presence became true, and the next
reply observed edit mode and an unnamed world. The global resource opener still
returned false, so pinned-world readiness and callbacks remained incomplete.
The exact source compiled and owned process exit was confirmed.

The current fixed candidate waits for that actual non-null API, then requests
`editor.SetOpenedResource(pinnedAbsolutePath)` once. This documented module method
had reached world loading in older attempts, but those attempts skipped explicit
module opening. The new precondition is now observed, not assumed. Both native
resource registration/path checks and all subsequent pinned-world/mode/trace
requirements remain intact. No generic-opener fallback occurs in this job.
`fixtures/previous-explicit-module-global-opener-rpc.c.txt` preserves the exact
12,506-byte preceding RPC, SHA-256
`c5d9edfdfb79d8b2cc911eeb06b605b80ec853bb85a2c41961da549723d8a08b`.
The post-open API diagnostic is also recomputed explicitly if the reacquired
module is null. This does not establish a callback or service capability.

At `build/component callbacks & spaces-7gdcd8fr/results.json`, this activated
module-specific candidate compiled. The initial response confirmed accepted
module opening and a non-null API. The next request logged the exact owned world
load, CreateEntities at 44.4227 ms and LoadWorld at 56.9505 ms, but its RPC timed
out after eight seconds. No readiness response, entity spawn or callback was
recorded; owned process exit was confirmed. Log absence of a selected world/VM
error does not diagnose the timeout's cause. The separate harmless dispatch
probe tests cooperative execution without opening anything; even a pass leaves
deferred native opening, reload stability and callback delivery unverified.

The experiment keeps the same time budgets, owned-session checks,
native addon/editor path resolution, explicit wire codec, authority guards,
callback observations and seven-case acceptance. Failure leaves its own gate
open; no missing world, authority, event or trace may be replaced with a success
flag. No source installation, live MESH edit or generated-file correction occurs.

The harmless GameCommon dispatch prerequisite subsequently passed all six cases
at `build/workbench dispatch & spaces-csb3u27_/result.json`. It establishes one
resumption after caller submission, without any native open. The new separately
frozen callback candidate submits one global worker, yields for 200 ms, then
reacquires and rechecks native editor/API/resource/world/mode identity before
one SetOpenedResource call. No editor reference crosses the yield. Five bounded
requested/submitted/entered/resumed/returned counters and separate acceptance
are exposed; readiness waits for returned=1 and accepted=true. Lost state cannot
resubmit. Confirmed exit of the exact owned process handles cancellation.
`fixtures/previous-explicit-module-sync-opener-rpc.c.txt` preserves the preceding
12,613-byte synchronous template, SHA-256
`c7f91fd70da71a51997b9b071ac13e17ed2b57a0d085eef032237ed62889dbfa`.
This deferred native experiment still needs its own actual receipt; sentinel
success does not establish native opening, reload survival or callbacks.

The deferred wire/state checkpoint passes 124 pure Python cases. Its new
PowerShell checker attempt remains incomplete because the configured host
stopped returning; requested host stop did not confirm exit. No new engine
compile or deferred native-open execution occurred after that interruption.
The cause is unknown, with no security-policy change or inferred policy denial.
Retain earlier actual engine receipts as historical scopes rather than applying
them to this new template. See `docs/BERYL_DELIVERY_STATE.md` for current evidence.

Current Python-only admission has 124 passing response/state cases plus 50
separate passing transport-envelope cases. It independently rejects absent
errors/schema/session checks, wrong process identity and reordered/incomplete
actions. Root prepared the exact deferred source candidate successfully at
`build/component callbacks & spaces-gxs19pd4/results.json`. Only private Beryl
source generation and immutable staging ran; the new trusted native-opening
template is not yet engine-compiled or executed. Public release gates stay open.
