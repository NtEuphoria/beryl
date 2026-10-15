# Native tablet initialization and stowed-frame transport

This is trusted experimental fixture source for `BerylTabletNativeCallbacks`.
It adds one handler to the separately prepared 92-file native tablet candidate.
The original 92 inputs, including the production tablet adapter and observer,
remain unchanged. This package does not install a public scenario or launch an
engine. Its handler has not yet been compiled or executed.

The experiment observes two engine-created component instances. It targets
native `OnPostInit` and at least three stowed `EOnFrame` calls per owner, with an
explicit upper bound of 200 frames per owner and 1,024 total observation rows.
It does not exercise Focus, SetHeld, gadget input, widgets, screen resources,
telemetry scheduling, player equipment, authority, multiplayer or deletion.
World exit can perform native teardown; this fixture neither requests native
entity deletion nor claims to verify teardown callback behavior.

The frozen observer invokes the unchanged production superclass from actual
engine callback overrides. This transport never calls a callback directly and
never constructs a native component with `new` or writes production state.
Fixture tokens identify owners 1 and 2; no portable identity uses an address.

## Identity and generation

The renderer substitutes only `@TOKEN@`, `@SOURCE_SHA256@` and
`@WORLD_ABSOLUTE@` in `rpc.c.in`. These are installed-tool inputs, not project
code strings. The source hash identifies the exact 92-file prepared manifest;
it excludes the additional RPC source to avoid self-reference. The token must
also bind the template, transport, semantic checker, engine and tool identities.
The runtime transport separately checks the exact 93-file staged manifest at
every RPC boundary. No input from the original candidate is overwritten.

The world alias and registered resource are distinct observations. Both must
resolve natively to the exact owned absolute world path:

- `$BerylTabletNativeStowedPrototype:worlds/BerylTabletNativeStowed.ent`
- `{BE71570A20261010}worlds/BerylTabletNativeStowed.ent`

The prefab is `{BE71570B20261010}Prefabs/BerylTabletNativeStowed.et`; it must
resolve as a valid native entity source. After the engine reports play mode,
spawning uses a freshly captured nonnull `GetGame().GetWorld()`. Each returned
owner must belong to that world, contain the observer, and match the pending
token's native registry claim before ACTIVE is set. The editor API world is not
substituted for the live Game world. No replication component or authority
contract is introduced.

The exact source basis, primary declaration hashes, row fields and operation
origins are in `source-contracts.json`. These declarations identify signatures;
they do not prove native delivery or lifecycle behavior. The source-linked
generic callback loader previously executed in its own scope. That evidence
does not establish this new handler's compilation or tablet runtime.

## Fixed action protocol

Requests contain exactly `token` and `action`. Installed actions are `load`,
`status`, `play`, `spawn` and `stop`; no arbitrary function/action is admitted.

- Phase 0 performs one module-open request and one yielded native world-load
  request. Load readiness requires the exact native named world and edit mode.
  Play readiness requires actual game mode, InPlayMode and a nonnull Game world.
- Phase 2 follows the two native spawns. Every response remains `pending`, even
  after `frames_ready` becomes true. The host then requests `stop` once.
- Phase 3 retains a scalar string prefix and asks the native editor to return
  to edit mode. A void switch return is not completion evidence. A later status
  must report the same owned world, edit mode, no game mode and no play.
- Phase 4 publishes the final trace only after that observation and checks for
  lost rows, changed prefixes, incomplete pairs, a registry reset and any later
  failure or exhausted frame budget. Frames arriving during handoff are included.
  Repeated complete responses must match the sealed final scalar trace.

The handler never dereferences retained owner or State objects after play. It
reads only registry array counts and plain observation fields. It adds no
strong engine reference across requests. The original observer still retains
at most two owner/State references; their broader lifetime behavior is unverified.

## Trace receipt

Each string row has exactly 18 pipe-delimited fields: zero-based sequence and
the frozen observer's 17 scalar fields, in their declared order. Boolean text
is literal `0` or `1`. Integers use native decimal output. Float observations
use native `float.ToString`; these are rounded finite observations, not verified
binary32 bit encodings or signed-zero proofs.

The checksum starts at zero and applies `h = (31*h + byte) % 1000003` to each
raw ASCII row byte followed by newline byte 10. No numeric JSON reserialization
participates in this checksum. Before final completion, `rows` and `caseIds`
remain empty and `row_count` and `checksum` remain zero. `frame_counts` is empty
before two owners exist and then contains two counts.

The final exact five IDs are `native.init.1`, `native.init.2`,
`native.stowed-frames.1`, `native.stowed-frames.2` and
`native.independent-state`. Publishing these names is not semantic acceptance.
The independent `scripts/verify-tablet-native-trace.py` checks the complete
raw trace, exact identity, ordered initialization, paired frames, state/mask
observations, minimum/maximum coverage and checksum. Its stricter pairing and
numeric admission apply even when the engine's prerequisite scan succeeds.

Raw NetAPI replies remain unchanged. The owning transport may separately
normalize JSON booleans encoded as literal booleans or exact numeric 0/1 and
documented empty-array omission. Completed replies require their full arrays;
an incomplete receipt, timeout, cancellation or startup failure never counts
as matching source behavior or completed native callbacks.

## Execution obligations

The parent-owned transport must use a fresh hidden process, an exact pinned
engine executable, mutex and PID/start/executable ownership checks, a listener
owned by that process, exact input hashes and unchanged tools around every RPC.
The fixed budgets are 30 seconds per stage, 8 seconds per RPC, at most 64 polls
per stage, 180 seconds overall and 5 seconds for confirmed owned cleanup.
No fallback, retry after an accepted failed request, source variant or timeout
widening is part of this experiment. Raw logs are captured after confirmed
owned process exit, with primary failures preserved.

Compilation, native callback execution and trace acceptance are separate
evidence levels. No source-only check closes a runtime, resource lifetime,
tablet services, multiplayer or whole-mod release gate.
