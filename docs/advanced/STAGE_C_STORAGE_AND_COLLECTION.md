# Stage C checkpoint: array ownership, Canvas observations and actual target collection

This packet records an experimental engine checkpoint. It does not admit terrain
pooling, replace live MESH source, or claim renderer/gameplay/Rust performance.
The [final installed checkpoint](../BERYL_ADVANCED_IMPLEMENTATION_STATE.md) now
records fresh receipts for compiler `aa7e9d51…d9b04` and the nineteen-file bundle.
Its separate 60-pair collection recorded 34.06% median paired reduction, with
zero slower pairs; it remains dependent and exploratory. Initial development
receipts below retain their original identities and are not pooled with it.
All engine execution uses the existing Workbench integration scripts and the
shared `Local\BerylOwnedWorkbenchSessionV1` mutex. Sessions belong to a unique
isolated candidate and are closed by verified PID plus start time.

## Scope and interfaces

The installed scenario registry now provides:

| Scenario | Admitted operation | Important boundary |
|---|---|---|
| `probe.array.storage` | Six fixed logical-storage and script-reference cases | Generic reference-array `.Copy` is not admitted; explicit element insertion is a separate operation |
| `probe.canvas.retention` | Positive weak-observer control and immediate script-reference lifetime around real widget publication/replacement/removal | Rendered consumption and native payload retention remain unavailable |
| `measure.terrain.construction` | A frozen exploratory schedule of preserved-reference/direct-v2 command construction and release | Sampling, setup, Canvas publication, rendering, other layers and MESH integration are outside the interval |

`beryl mod verify --scenario measure.terrain.construction --artifact <id>
--measurement-plan <schedule.json> --workbench-tools <plugin>` accepts typed
schedule data. It accepts no embedded code, commands or arbitrary callbacks.
Schedules must be exploratory, contain admitted terrain cases, have 30–120 pairs
balanced separately for each fixture, and request 1–32 operations per interval.
The command rejects altered ordering, unknown fields, repeated options and
conflicting case/count arguments. Other scenarios reject `--measurement-plan`.

The current tool bundle has nineteen exact files. The loader also recognizes
the previous exact four-, eight-, thirteen- and sixteen-file sets. Previous
loaders are identified by complete bytes, backed up before replacement, and
retained version directories permit rollback. An unrecognized loader or changed
template fails before dispatch. The sixteen-file set was an intermediate tested
array/Canvas checkpoint; it remains readable rather than being silently orphaned.

## Installed engine evidence and contracts

The initial actual runs used Workbench `1.8.0.13`, executable SHA-256
`7dd36ca1f662b0c13669a4f2f7f10e3c461c2906b021e742272d64b3ab7e9798`,
and compiler SHA-256
`99f10cf5e818e5a8f509fd3505146500b8a2ce4730aece6cbbcdb96c8ee171e5`.
Later compiler checkpoints require their own receipts; these identities cannot
be relabeled after a rebuild.

Installed API documentation is under
`C:/Program Files (x86)/Steam/steamapps/common/Arma Reforger Tools/Workbench/docs/EnfusionScriptAPI/html/`.
Relevant declarations are `interfacearray-1-g.html`, `interfaceCanvasWidget.html`,
`interfaceTriMeshDrawCommand.html`, `interfaceWidgetType.html`,
`interfaceWorkspaceWidget.html`, `interfaceWidget.html`, `interfaceGame.html`,
`interfaceColor.html`, and `interfaceSystem.html`. The actual compile/runtime
receipts establish exercised signatures on this engine build; generated API
declarations alone do not establish lifetime guarantees.

Bohemia documents reference counting, strong local variables, weak class fields
unless marked `ref`, and the distinction between strong and weak array elements.
The probe uses those rules to avoid accidentally retaining an observed object.
[Bohemia: Scripting—Automatic Reference Counting](https://community.bistudio.com/wiki/Arma_Reforger%3AScripting%3A_Automatic_Reference_Counting).

### Array observations

The installed array probe performs **36 checked observations across six cases**:

1. Scalar array assignment aliases the original array; `array<int>.Copy` creates
   independent outer scalar storage. Mutation and clearing distinguish the two.
2. Explicitly inserting a reference element into a second strong-element array
   shares the object identity and its mutable field. Clearing the first array
   preserves the object; clearing the last strong container expires the weak
   observer and invokes the tracked destructor once.
3. Inserting into a weak-element array does not preserve the object beyond the
   helper's strong local scope. The slot remains present but null. Clearing the
   slot does not invoke a second destruction.
4. Explicit insertion of an inner array into two outer strong-element arrays
   shares that inner array. The outer collections remain separately mutable.
5. `Remove(1)` replaces the removed slot with the final element in the tested
   four-element array; `RemoveOrdered(1)` preserves the remaining order.
6. `Reserve` preserves logical count/content, extending `Resize` produces zero
   integer elements, `Clear` and `Compact` leave logical count zero, insertion
   remains usable, and shrinking a strong-element array releases its element.

The first attempted fixture used `.Copy` directly on `array<ref Tracked>` and
`array<ref array<int>>`. Workbench rejected both: its formal `array<T>` argument
did not accept these actual `array<@T>` instantiations. This is preserved evidence,
not a runtime ownership result. The corrected reference-element cases explicitly
use enumeration and `Insert`; they must not be described as successful generic
`.Copy` tests. The compiler's separate admission fix rejects corresponding
unsupported generated struct-copy shapes until a correct implementation exists.

The failed compilation is retained at
`build/storage-scenarios & spaces-88gkfu1j/result.json`, with project diagnostics
at generated lines 103 and 138. The successful installed probe is retained at
`build/storage-scenarios & spaces-x40qqqo0/result.json`.

### Physical-storage observation is separate

The development capability probe called installed `System.MemoryAllocationCount`
and `System.MemoryAllocationKB` around a 262,144-integer reservation. It observed
560,154 KB before reservation, 561,178 KB after reservation and through
`Resize`/`Clear`, then 560,154 KB after `Compact`. The raw allocation-count
snapshots were 1,886,253, 1,886,255 and 1,886,256 at different points.

These are **whole-engine snapshots**. They do not establish per-array physical
allocation counts, peak memory, a monotonic counter interpretation, allocator
reuse, or a universal release-size law. They agree with the documented logical
distinction between clearing elements and compacting unused capacity in this
one observation. No unknown physical measurement is converted to zero.

Evidence: `build/engine-caps-_asv1f_a/result.json`, including generated script,
raw compilation/runtime records and exact engine identity. No public capacity
getter was established. `MemoryStatsSnapshot` declarations were located, but no
verified capture/factory workflow was established and none is advertised.

### Canvas: what the native call did and what remains unknown

The operational probe performs **30 observations across two cases**. First, a
strong script-held command array keeps the tracked command and vertex array
visible to weak fields. Clearing and dropping that control array expires the
corresponding observations and increments the command destructor once. This
positive/negative control prevents an always-null observer from passing.

The second case creates a real `CanvasWidget` through
`GetGame().GetWorkspace().CreateWidgetInWorkspace`, using the installed
`WidgetType.CanvasWidgetTypeID` declaration. A helper publishes a tracked
`TriMeshDrawCommand` with a complete quad, then relinquishes all strong script
locals. The outer array, command and vertices are already absent from the weak
observer immediately after the helper returns. Replacing commands with an empty
array preserves that expired state. A second publication increments destruction
to two; widget removal leaves both tracked commands destroyed.

Actual observations therefore establish that these calls did not keep a strong
script reference to the submitted tracked graph in the tested synchronous
Workbench RPC path. They do **not** distinguish native payload copying from
discarded work, prove that the tracked subclass was rendered, establish a frame
boundary, validate pixel content, or authorize mutation/reuse of published
buffers. No graphics readback or rendered-consumption receipt exists here.
The receipt explicitly marks native consumer lifetime and pooling admission
unavailable. Holding graph references inside a handler would not repair that gap.

The initial development observation is in
`build/canvas-caps-3pn5iyr2/result.json`; the installed probe with observer control
is in `build/storage-scenarios & spaces-x40qqqo0/result.json`.

## Direct-v2 construction candidate

The preserved reference remains the complete current MESH terrain source,
SHA-256 `407074e33a42e971f7d05a445e65996911e277d99e24642260a760e5ff61e317`.
Only staged class/constructor identifiers are changed. `BuildRelief` and
`EmitChunked` remain unedited. The original direct candidate is retained
byte-for-byte in `terrain-adapter-v1.c.txt`.

V2 removes a prototype-specific excess: v1 calculated the band color once for
every new mesh chunk, while the reference calculates it once for each populated
band. V2 stores that color in the existing per-band holder when its first chunk
is created. It retains the same `BandColour`/`WaterColour` calls and conversion
arithmetic. It introduces neither pooling nor altered terrain classifications.

Semantic receipts continue to compare all admitted public fields:
`m_iColor`, every `m_Vertices` value, every `m_Indices` value, `m_fUVScale`,
`m_pTexture`, plus command ordering and an independent quad-winding oracle.
The six datasets each contain 6,400 cached samples and produce 6,241 quads /
12,482 triangles. Full comparison performs 750,095 checks. Float comparisons are
the engine's `==`, with adjacent-value probes; no bitwise equality claim follows.

Both semantic and measurement receipts now include exact source-template hashes
and identical dataset descriptors. The measurement importer rejects different
templates, datasets, compiler/tool identities, engine identity, source/artifact
identity, raw logs or staged-source manifests. A valid old-v1 comparison cannot
silently validate a new-v2 timing run.

## Measurement protocol and its limits

The initial schedule is fixed before execution: six cases, 60 pairs, 120 ordered
intervals, eight full construction/release operations per interval. AB/BA order
is balanced separately for every case. The 960 operations run in one owned
Workbench session and are **dependent observations**, not 60 independent trials.

Each batch prepares its finite cached-height fixture outside the timed region.
The measured loop creates a fresh output-command array, invokes the selected
reference or direct constructor, observes the command count, and releases the
graph before returning. This includes command, vertex and index construction
and script reference-count release. It excludes fixture construction/destruction,
height generation/capture, live engine sampling, Canvas publication and rendering.
There is no assertion that the excluded costs are zero for the application.

`System.GetTickCount` supplies integer milliseconds. Four explicit timer probes
precede the workload and at least one must advance. Backwards, wrapped,
overlapping or malformed intervals fail. Observed increments do not establish
clock resolution; multiplying to nanoseconds changes units, not precision.
Zero-length measurements remain visible and block interpreting them as resolved.
Raw whole-engine memory counters are recorded outside the timed region and are
not converted into allocation, retained-memory or peak-memory metrics.

The installed runtime response is exact, versioned `beryl.performance.target`.
It carries the compiled token, scope, timer API, completion fields, and every
scheduled row. Missing, reordered, extra or malformed rows fail. The importer
also requires a separately executed complete semantic comparison on the same
source templates and datasets. A measurement receipt alone is not a correctness
or adoption receipt. [`COLLECTOR.md`](../../tools/beryl-experiments/COLLECTOR.md)
defines the raw protocol and immutable journal checks.

The first timing-handler compilation hit EnforceScript's expression-complexity
limit while formatting a long receipt row. No timing executed in that failed
attempt. Formatting was split into bounded expressions **after** the timed
region, with no change to construction operations or schedule selection.
Evidence is retained at `build/terrain-measurement & spaces-a9w8o48i/result.json`.

### Initial actual collected batch

The next attempt completed the same full v2 payload comparison and all 120
scheduled intervals. It used an explicit immutable trusted tool snapshot, tool
SHA-256 `6641a45fd8936d7e52185b50e627ddc7b2e07b83ddf3c2d01d863badba9f4f97`.
The future verifier also exercises installation before execution. Compilation and
the raw measurement operation succeeded; the first journal import rejected an
absolute environment-evidence reference. A new relative-path descriptor repaired
only metadata, preserving the original failed import record and every target
measurement. No additional timing was selected or discarded during that repair.

The successful journal is
`build/terrain-measurement & spaces-bhegr908/collection-v2/journal/collection.json`,
SHA-256 `31d47d32a9167b2b08cf4c9d63f76dcee761e746add4bf78e25d9f48582621b0`.
`import-repair.json` records successful import and replay. The original
`measurement-result.json`, `semantic-result.json`, source templates, source
manifests, raw engine responses, schedule and compiler identity remain retained.

The descriptive median paired reduction for these dependent observations was
`499 / 1500`, approximately **33.3%**. Two of the sixty pairs were slower for
the candidate. No confidence interval or adoption decision is produced.

| Fixture | Median reference batch, ms | Median candidate batch, ms | Median paired reduction |
|---|---:|---:|---:|
| `flat_water` | 203 | 132.5 | 34.683% |
| `flat_land` | 209 | 138.5 | 32.762% |
| `sea_threshold_checker` | 206 | 133 | 35.071% |
| `row_column_ramp` | 212.5 | 142.5 | 32.148% |
| `mixed_integer_seed` | 207 | 145 | 32.031% |
| `narrow_height_range` | 210.5 | 139 | 33.727% |

Each batch contains eight operations. The table takes medians of recorded
integer-millisecond batch intervals; half-unit medians are averages of middle
observations, not an assertion of sub-millisecond timer precision. Paired
reductions are computed per pair before taking their median, so they need not
equal the ratio of the two marginal medians. All intervals advanced. Timer
calibration observed 14, 13, 14 and 15 ms; resolution remains unknown.

These results justify pursuing the construction hypothesis. They do not
establish a general renderer speedup, reduced peak memory, safe pooling,
independent statistical confidence, or a comparison against Rust.

## Verification and next admission gate

`scripts/verify-storage-scenarios.py` checks typed selection, malformed replies,
recomputed-checksum semantic mutations, installed-template tampering, prior
thirteen-file rollback and actual array/Canvas execution when requested.
`scripts/verify-terrain-measurement.py` checks malformed schedules, code-like
identifiers, operation/pair budgets, altered ordering, malformed/wrapped counters,
missing rows and nonadvancing clocks, then executes semantic comparison and the
frozen target schedule when Workbench is selected. Synthetic policy fixtures are
never counted as engine execution.

The next admission step must establish a rendered native-consumer lifecycle,
physical resource instrumentation, complete paid application scope, a visual
comparison and isolated MESH integration. Independent sessions or a reviewed
equivalent reset protocol, a baseline-only pilot, frozen selection policy and
held-out performance evaluation remain necessary before an adoption claim.
The new collector explicitly preserves those gaps instead of exporting partial
measurements as a passing performance experiment.
