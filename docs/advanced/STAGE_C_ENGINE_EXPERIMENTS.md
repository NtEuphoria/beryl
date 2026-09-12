# Stage C: isolated Enfusion experiments

Date: 2026-09-07. These are application fixtures run through installed local
tooling. They do not enable compiler transformations or modify live MESH.
Authoritative artifact/compiler/tool hashes and results are recorded in
[the execution state](../BERYL_ADVANCED_IMPLEMENTATION_STATE.md) and raw receipts.

## C1: ordered map traversal

The installed `probe.map.cursor` scenario compares indexed traversal with the
actual engine iterator interface. Its histories cover empty maps, insertion,
replacement, removal, reinsertion and reverse insertion. Every compared item
includes its key and fixture-generated reference token; the engine also compares
the actual object references. Portable traces never use memory addresses.

```text
beryl mod verify --project <project> --artifact <id> --scenario probe.map.cursor --scenario-count 64 --workbench-tools <plugin>
```

The count parameter admits 1–4,096 entries. `--scenario-case` may select a
nonempty unique subset of installed case names. Unknown cases, duplicate cases,
wrong tokens, unexpected rows, incomplete results and checksum mismatches fail.

The current semantic evidence covers six histories at counts 1 and 64. It does
not establish iterator complexity, traversal speed, order under every possible
history, or safety while a cursor is active during mutation. The probe completes
mutations before comparing traversals. Production enumeration is unchanged.

Before adopting C1, measure the required 16/64/256/1,024/4,096 sizes and complete
queries under the frozen measurement protocol. Retain indexed traversal if the
actual ordered key/reference contract differs. Sorting changes that contract and
is not an acceptable repair.

## C3: direct terrain chunk construction

The installed `compare.terrain.chunks` scenario exercises relief command
construction using a complete 80×80 cached height grid. It deliberately stops
before Canvas publication. Sampling, the other map layers and whole rendering
remain outside its implemented comparison scope.

```text
beryl mod verify --project <project> --artifact <id> --scenario compare.terrain.chunks --workbench-tools <plugin>
```

Fixed installed case IDs are:

| Case | Input purpose |
|---|---|
| `flat_water` | All-water band, 1920×1080 pane |
| `flat_land` | Flat land, 3440×1440 pane |
| `sea_threshold_checker` | Sea-threshold neighborhoods, 2×2 pane |
| `row_column_ramp` | Multiple bands and asymmetric axes, 1919×1079 pane |
| `mixed_integer_seed` | Deterministic mixed heights, 3440×1440 pane |
| `narrow_height_range` | Minimum-range branch, 4095×2047 pane |

`--scenario-case` selects a nonempty unique subset. `--scenario-count` and
`--stage` are rejected for this scenario. Project descriptions cannot inject
height-generating scripts or arbitrary engine strings.

### Reference and candidate

`tools/beryl-mod/terrain-reference.c.txt` retains the original complete
`SPK_TerrainMap.c` bytes outside production script discovery. Its provenance file
records the source path and SHA-256. Staging renames only the original class and
constructor so the preserved implementation and candidate can coexist. The
adapter invokes the inherited original `BuildRelief` and `EmitChunked` behavior.
Changing the preserved bytes without matching reviewed provenance fails staging.

`terrain-adapter.c.in` constructs final `TriMeshDrawCommand` chunks directly,
using one current chunk per band and a 240-quad maximum. It retains the original
cell evaluation and expression grouping, then publishes command references in
band order with row-major quads within each band. It does not pool arrays across
renders or mutate arrays after passing them to Canvas.

The expected opportunity is removing intermediate payload storage and copying.
This is a hypothesis until paid construction costs and actual retained/peak
memory are measured. New bookkeeping also has a cost. Logical payload sizes
cannot be presented as engine allocator measurements.

The initial v1 prototype creates eight band holders and computes the color for
each new chunk; it is retained in `terrain-adapter-v1.c.txt`. The current v2
adapter caches that same color once per populated band, matching the reference's
conversion frequency. Both preserve the same command payload. The newer
[storage and collection checkpoint](STAGE_C_STORAGE_AND_COLLECTION.md) records
separate v2 semantic evidence and exploratory construction/release intervals;
the earlier v1 receipts must not be relabeled as v2 measurements.

### Comparison contract

Both command graphs remain alive until all comparisons finish. The handler
checks the five public payload fields listed by the installed engine API:
`m_iColor`, `m_Vertices`, `m_Indices`, `m_fUVScale`, and `m_pTexture`.
It also checks command sequence, per-command sizes, the 240-quad limit, complete
vertex and index values, and independently specified index winding.

Python fixtures compute dataset fingerprints, band counts and expected command
metadata. The engine independently constructs its grid and checks its fixture
checksum. Every dataset contains 6,241 quads and 12,482 triangles. Command count
depends on band distribution; it is not fixed by those totals alone.

Floating values are compared with the engine equality operator. Probes confirm
that the chosen adjacent values near 1 and 16,777,216 compare differently on the
tested engine. Positive and negative zero compare equal. This is **not** verified
bit encoding or universal bitwise floating-point equivalence. Nonfinite grids
are outside this fixture's admission domain.

The receipt includes exact cases, ordered trace count/checksum, source and tool
identity, engine identity, raw logs and comparison scope. A changed-vertex
mutant must fail without receiving a successful semantic receipt. Synthetic
reply-corruption tests exercise malformed, partial and stale result rejection.

### Remaining adoption gates

1. Freeze the complete construction/render workload and baseline before timing.
2. Verify the consumer lifetime needed by any production change. No cross-render
   reuse is admitted through this experiment.
3. Collect at least 30 independent paired blocks, balanced in execution order,
   including setup, command conversion, cleanup and other paid work.
4. Measure actual memory where the engine exposes that capability. Otherwise
   keep the corresponding resource gate unavailable.
5. Compare full layer ordering and perform visual/interaction review in an
   isolated MESH candidate at ultrawide and 1920×1080 resolutions.
6. Adopt only if semantic, resource and practical-improvement gates pass.

The fixed-grid payload experiment alone does not close C3 or Stage C.

## Shared execution and rollback

The scenarios extend the existing Workbench bridge. A cross-process session gate
serializes engine work. The job verifies engine/tool/project/artifact identity,
starts and stops only its own session, and retains raw failures. Timeout,
cancellation, stale sources and unavailable capabilities remain distinct outcomes.

Versioned tool installation supports the original four-file bundle, the
eight-file map/source-map bundle, the thirteen-file terrain bundle, the
sixteen-file storage checkpoint and the current nineteen-file collection bundle. Exact
loader checks and prior-loader backups preserve rollback. An unknown loader is
not overwritten. Compiler-owned generated files remain separate from handwritten
MESH resources.

## Other Stage C experiments

C2 query intermediate elimination and C4 sensor scan generations remain
unimplemented. Their append behavior, duplicate resolution, acquisition/cap
ordering, freshness updates, visibility stamping, repeated dwell accumulation
and swap-removal obligations remain those in
[the advanced plan](../BERYL_ADVANCED_IMPLEMENTATION_PLAN.md). Success of the
terrain or cursor fixture does not provide these missing contracts.
