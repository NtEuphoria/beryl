# Tablet native init and stowed-frame preparation

This trusted test package observes the **unchanged production Beryl-authored
`SPK_TabletComponent`** through a distinct derived component. Its only callback
overrides are `OnPostInit` and `EOnFrame`; each invokes its production superclass
once. The source contains no manually delivered callback or constructor, no
`Focus`, `SetHeld`, UI opening, gadget activation, input registration or deletion.

`prepare-tablet-native-callbacks.py` only validates and copies a pinned successful
`tablet-suites-v1` source candidate into a new build workspace. It renders actual
emitted State/field identities from that candidate's source map. It never invokes
the compiler, native executable, PowerShell, Workbench or a model API.

The composition contains only the derived tablet observer. It excludes
DroneInput, TabletGadget, inventory, editable-entity, mesh and replication
components. This is an explicit experimental composition change, not the original
six-component tablet prefab. The original prefab and implementation stay retained
in the source evidence. All existing candidate scripts and 28 selected resources
remain unchanged; the candidate has a distinct addon identity and six new files.

The `.ent`/layer payload matches the verified minimal layered-world source format.
The new name and resource identifiers are private fixture assignments. Their
native registration, type and loadability remain unverified until a separately
admitted engine job checks the exact staged addon. Base-game dependency and exact
original candidate source closure remain unchanged.

No runtime transport is provided yet. A future installed harness must establish
owned editor/game-world identity, enter play, set a pending token immediately
before each of two native `SpawnEntityPrefab` operations into `GetGame().GetWorld()`,
and use the separately verified active-owner/frame-event conditions. It must never
call these callback overrides manually. Registry exhaustion or invalid tokens are
observable failures; they do not suppress the production superclass callback.

Observation coverage is initialization and STOWED frames only. The initial fresh
state does not independently prove reset of a nonzero state; a present FRAME bit
does not prove the mask setter executed exactly once. Source analysis and later
runtime traces must retain those distinctions. The registry deliberately retains
at most two owner/state references and up to 1,024 observation records for this
bounded experiment; it proves neither deletion cleanup nor unrestricted lifetime.
The proposed future scenario must predeclare at least three and at most 200
frames per owner. Two owners at that maximum produce 804 before/after records,
within the row budget. Exhaustion records a failure, freezes the observer ordinal
and still invokes the production frame callback; dropped rows cannot be accepted
as a successful trace. Independence is explicitly unavailable before both states
are observed. Both worlds must be nonnull before their equality is reported.

The exact original tablet source is retained as a behavioral reference input.
It is not renamed, emitted as a second production class or executed by this
preparer. Binary32 serialization, original/generated engine parity, public service
calls, native deletion, profile isolation, real player ownership/equipment,
handler/resource lifetime, visual behavior and multiplayer remain open gates.

See `docs/advanced/P5_TABLET_NATIVE_LIFECYCLE_ADMISSION.md` for the independent
acceptance ladder. Source preparation success means the frozen files were admitted
and copied accurately; it is not an engine or native-callback result.
