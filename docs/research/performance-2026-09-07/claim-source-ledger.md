# Claim-to-source ledger

Internal research record, 2026-09-07. User-facing deliverable: `docs/BERYL_PERFORMANCE_RESEARCH_2026-09-07.md`.

Primary sources only support technical conclusions. Unmeasured Beryl mechanisms are labeled hypotheses in the report. Source-derived operation counts are not profiler measurements. All online access dates are 2026-09-07. Confidence below concerns what the source establishes, not expected Beryl performance.

## Local evidence

The companion `source-fingerprints.json` records 152 inspected/relevant input-file hashes, including Beryl source/runtime/tooling and MESH script files. This is an input snapshot, not a claim that every file was exhaustively audited or benchmarked. Existing result artifacts were read separately under read-only approval where sandbox access required it.

| Claim | Primary local evidence | Assessment / limitation |
|---|---|---|
| M3 isolated candidate passed; M4–M8 and independent multiplayer incomplete | `docs/SPARKOS_IMPLEMENTATION_STATE.md`; `build/mesh-pid-ej8h72g_/result.json` | Existing recorded evidence; no new engine execution |
| Current native flags and source-unit structure | `src/driver/build.c:87–112` | Root/agent source inspection; downstream machine behavior not measured |
| Map indexed traversal occurs on store/query/sweep paths | MESH `Core/SPK_MeshStore.c:63–96`; `Query/SPK_EntityQuery.c:67–69` | Independently read; combine with E1 only for a complexity concern |
| Five temporary container sites in current single-store-provider marker path | MESH marker/query/provider functions cited in report H02 | Counted construction sites; not allocation timing or peak-memory evidence |
| Strict-newer winners; equal timestamps preserve first encountered entry | MESH `Query/SPK_EntityQuery.c:57–63` | Actual source governs; a nearby order-independence comment is insufficient |
| Marker cap increments after slot/root acquisition even when symbol rendering fails | MESH `UI/SPK_MarkerLayer.c:158–182,237–247` | Agent review corrected initial imprecise wording; preserve counter/control flow |
| Freshness changes with time without publication | MESH `UI/SPK_MarkerLayer.c:115–127` | Prevents whole-update skipping from store-version equality |
| Terrain emits 6,241 quads; intermediate inserts 49,928 floats and 37,446 integers | MESH `UI/SPK_TerrainMap.c:336–458`, GRID=80 | Arithmetic from loop bodies; not memory bytes, timings, or FPS |
| Scan stamps must precede NONE classification rejection | MESH `Sensors/SPK_SensorComponent.c:456–461,498–535` | Source behavior; duplicate evaluation and array alignment retained |
| Positive expiry boundary and shared alias constraints | MESH `Core/SPK_MeshEntity.c:9–33`; store Get/Publish/Sweep | Root and incremental agent independently read; mutation interception incomplete |
| Existing blueprint already covers most broad optimizer families | `docs/BERYL_OPTIMIZATION_AND_ENFUSION_BLUEPRINT.md` §§9,13,15–21,46 | This report presents refinements and new local applications, not unsupported novelty |
| Historical benchmark claims unusable as current evidence | `docs/BENCHMARKS.md` warning; `scripts/bench.sh` | No old timing or claimed checked-overflow percentage reused |

## External primary evidence

| ID | Title / author or publisher | Date / URL | Supported claim | Access and verification limits |
|---|---|---|---|---|
| E1 | map Interface Template Reference / Bohemia Interactive | Undated generated API; https://community.bistudio.com/wikidata/external-data/arma-reforger/EnfusionScriptAPIPublic/interfacemap.html | Indexed GetElement/GetKey O(n); iterators declared | Root and agent read; installed Workbench HTML corroborates. Iterator complexity, order and invalidation unknown |
| E2 | array Interface Template Reference / Bohemia Interactive | Undated generated API; https://community.bistudio.com/wikidata/external-data/arma-reforger/EnfusionScriptAPIPublic/interfacearray-1-g.html | Clear retains backing allocation; Reserve; Remove fills hole with final element | Root and agent read; installed HTML corroborates. Does not establish Beryl nested value semantics |
| E3 | CanvasWidget Interface Reference / Bohemia Interactive | Undated generated API; https://community.bistudio.com/wikidata/external-data/arma-reforger/EnfusionScriptAPIPublic/interfaceCanvasWidget.html | Caller retains array; batching restrictions | Root and agent read. Consumer retirement and concurrent mutation timing unverified |
| E4 | Script Profiling / Bohemia Interactive | Undated retrieved wiki; https://community.bistudio.com/wiki/Arma_Reforger%3AScript_Profiling | Script profiling and allocation inspection discovery | Agent obtained substantive indexed official content; direct wiki access limitations. Installed modes/overhead not tested |
| R1 | Profiles / Rust project | Rolling; https://doc.rust-lang.org/cargo/reference/profiles.html | Overflow, panic, optimization and LTO configurable | Root read. Configurations must be explicitly matched in future experiments |
| R2 | Unsafe Rust / Rust project | Rolling; https://doc.rust-lang.org/book/ch20-01-unsafe-rust.html | Unsafe does not disable borrow checking | Root read; no broad language-superiority inference |
| I1 | Incremental lambda-Calculus in Cache-Transfer Style / Giarrusso, Régis-Gianas, Schuster | ESOP 2019; https://link.springer.com/chapter/10.1007/978-3-030-17184-1_20 | Explicit intermediate caches address derivative recomputation | Root and agent read publisher abstract/metadata; no claim of full proof reconstruction |
| I2 | Adapton: Composable, Demand-Driven Incremental Computation / Hammer, Phang, Hicks, Foster | PLDI 2014; https://www.cs.umd.edu/projects/PL/adapton/ | Dirtying, demand repair, overhead/retention relevance | Agent author-paper/artifact review; root read project. Linked draft has 2013 internal date; publication identity from PLDI project |
| I3 | Incremental Computation with Names / Hammer, Dunfield, Headley, Labich, Foster, Hicks, Van Horn | OOPSLA 2015; arXiv v6 2021; https://arxiv.org/html/1503.07792v6 | Names, consistency, Appendix A weak-edge cache reclamation counterexample | Root and agent independently read crucial appendix. Particular reclamation solution not transplanted automatically |
| I4 | Differential Dataflow / TimelyDataflow maintainers; original paper McSherry et al. | CIDR 2013 paper, rolling Rust project; https://github.com/TimelyDataflow/differential-dataflow | Incremental dataflow available in Rust | Agent read original paper/project; report uses bounded claim. No need for partial-order runtime in initial Beryl design |
| I5 | Kinetic Data Structures: Animating Proofs Through Time / Basch, Comba, Guibas, Hershberger, Silverstein, Zhang | SoCG video proceedings June 1999; https://graphics.stanford.edu/~comba/papers/socg.pdf | Maintained certificates establish results until invalidated | Root and agent read two-page overview. Author publication page supplies date. No finite-precision/engine-motion guarantee |
| N1 | Bufferization / LLVM-MLIR project | Rolling; https://mlir.llvm.org/docs/Bufferization/ | Destination and in-place buffer analysis | Root and agent read. Tensor model differs from Beryl owning values |
| N2 | Ownership-based Buffer Deallocation / LLVM-MLIR project | Rolling; https://mlir.llvm.org/docs/OwnershipBasedBufferDeallocation/ | Deallocation separate; unsimplified generic alias checks can be quadratic | Root and agent independently checked lines 29–70. Not Beryl measurements |
| N3 | Perceus: Garbage Free Reference Counting with Reuse / Reinking, Xie, de Moura, Leijen | PLDI June 2021; https://www.microsoft.com/en-us/research/uploads/prod/2021/06/perceus-pldi21.pdf | Reuse and sharing/retention tradeoffs | Agent read relevant sections; root inspected primary PDF. Refcounted functional model differs from current Beryl |
| N4 | Auto-Vectorization in LLVM / LLVM project | Rolling; https://llvm.org/docs/Vectorizers.html | Existing runtime alias checks, diagnostics and target-dependent vectorization | Root and agent checked. Efficient installed lowering still an experiment |
| N5 | LLVM Language Reference / LLVM project | Rolling; https://llvm.org/docs/LangRef.html | nsw/nuw poison semantics; vector overflow intrinsics | Root and agent verified relevant sections. No efficient-codegen guarantee |
| N6 | Halide: A Language and Compiler for Optimizing Parallelism, Locality, and Recomputation in Image Processing Pipelines / Ragan-Kelley et al. | PLDI June 2013; https://people.csail.mit.edu/jrk/halide-pldi13.pdf | Algorithm/schedule tradeoffs | Agent read primary PDF. Report transfers the research direction, no benchmark magnitudes |
| N7 | Clang Compiler User's Manual / LLVM project | Rolling; https://clang.llvm.org/docs/UsersManual.html#profile-guided-optimization | PGO and representative training | Agent primary review; installed-version support needs local probe |
| N8 | ThinLTO / LLVM project | Rolling; https://clang.llvm.org/docs/ThinLTO.html | Cross-module optimization mechanism | Agent primary review; root synthesis notes limited current translation-unit boundary |
| N9 | Profile-guided Optimization / Rust project | Rolling; https://doc.rust-lang.org/rustc/profile-guided-optimization.html | LLVM PGO support and matching compilation conditions | Root and agent read. PGO is not unique to Beryl |
| V1 | egg: Fast and Extensible Equality Saturation / Willsey et al. | POPL 2021; https://popl21.sigplan.org/details/POPL-2021-research-papers/23/egg-Fast-and-Extensible-Equality-Saturation | Equality-saturation search precedent | Root read conference primary record. Beryl rewrite legality requires its own contracts |
| V2 | Alive2: Bounded Translation Validation for LLVM / Lopes, Lee, Hur, Liu, Regehr | PLDI June 2021; https://web.ist.utl.pt/nuno.lopes/pubs.php?id=alive2-pldi21 | Bounded LLVM translation validation and incompleteness | Root and incremental agent read author record. Does not validate Enfusion or Beryl end to end |
| M1 | Rigorous Benchmarking in Reasonable Time / Kalibera, Jones | ISMM 2013; https://kar.kent.ac.uk/33611/ | Hierarchical repetition and uncertainty motivation | Repository search-visible abstract/metadata read; full text/open timed out. Report explicitly discloses limitation |
| M2 | Coz / Curtsinger, Berger, project maintainers | SOSP 2015 paper; rolling repository; https://github.com/plasma-umass/coz | Causal optimization value differs from time attribution | Root read project; no verified Windows/Enfusion integration claimed |

Rolling LLVM pages can describe a development revision newer than installed Clang 22.1.6. Generated Doxygen version strings are not Enfusion engine versions. Existing local integration records identify Workbench 1.8.0.13; no new installed-engine validation was performed.

## Synthesis and disconfirmation

- Prioritize iterator probes over assuming foreach is efficient or order-compatible.
- Preserve merge-before-filter and actual marker counter behavior; no early raw-candidate cap.
- Prefer a conservative deadline bound before a heap; stale early bounds waste work safely, unknown earlier writes are unsound.
- Admit lazy derivations only when skipped work is total/non-observing under its resource profile.
- Initial demand regions do not share dependencies across eviction boundaries.
- Result-stability guards must themselves be total/non-observing; failed proof is ordinary fallback.
- Diagnostic instrumentation can prevent optimizations; semantic operation counts do not establish optimized machine work.
- General algorithmic techniques remain available to Rust; matched baselines are mandatory.

The three agents performed a bounded second review of the canonical report. Six material tightening themes were incorporated: marker cap behavior, join pre-update convention, deferred-work totality, cross-region eviction, guard totality, and diagnostic-counter interpretation. No code edits were made by the agents.

## Stop rationale

Discovery covered actual source constraints, primary mechanisms, counterexamples, and fair experimental baselines. Remaining high-impact gaps require installed-engine probes, mutation/lifetime contracts, or measurements. Additional broad literature search would not establish those facts. Research stops with these gaps explicit rather than treating theoretical applicability as performance evidence.
