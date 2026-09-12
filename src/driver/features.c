#include "features.h"
#include "../common/hash.h"
#include "../common/json.h"
#include <string.h>

/* Test links identify suites to run; they are never success receipts. The
 * positive/negative descriptions record obligations, not execution results. */
static const FeatureTestGroup test_groups[] = {
    {"modules", "tests/unit/test_modules.c", "qualified declarations, imports and receiver identity", "private access, ambiguous imports and declaration conflicts"},
    {"values", "tests/unit/test_ownership.c", "initialization, plain-value modes and disjoint access", "uninitialized reads, moves and overlapping call access"},
    {"native", "scripts/verify-foundation.py", "generated programs at O0/O2", "checked overflow, bounds and division failures"},
    {"reference", "scripts/verify-reference.py", "bounded reference and differential programs", "unsupported programs and exhausted budgets"},
    {"destinations", "scripts/verify-reference-destinations.py", "safe projected assignment and full PID", "overlapping destination mutations rejected before execution"},
    {"traps", "scripts/verify-expected-traps.py", "expected source traps and successful observation prefixes", "wrong site, missing trap and changed observation prefix"},
    {"security", "scripts/verify-taint.py", "bounded field/element/call provenance and fixed-array interval proofs", "laundering, helper sinks, propagated errors and secret control; no complete security or runtime authority claim"},
    {"allocation", "scripts/verify-allocation.py", "checked arena/vector/string/map and native List growth", "size overflow, capacity overflow and injected allocation failure"},
    {"enfusion", "tests/unit/test_enfusion.c", "admitted EnforceScript generation", "unsupported types and reference-array copy fields"},
    {"driver", "scripts/verify-driver.py", "explicit argv and isolated native jobs", "failed writes, failed launch, timeout, cancellation and stale publication"},
    {"context", "scripts/verify-context.py", "resolved signatures, modes, defaults and source identity", "ambiguous names, unknown names and unavailable bindings"},
    {"bindings", "scripts/verify-binding-registry.py", "exact selected declaration fragments and matching identities", "missing or mismatched engine/API bytes"},
    {"native_evidence", "scripts/verify-native-evidence.py", "generated C, arguments and requested compiler artifacts", "unsupported lowering and malformed evidence options"},
    {"maps", "scripts/verify-source-map-diagnostics.py", "generated-line mapping with retained raw diagnostics", "stale artifacts, source mismatches and unmappable columns"},
    {"mod", "scripts/verify-mod.py", "strict companion validation, isolated build and guarded promotion", "unknown fields, missing symbols, changed output and rollback conflicts"},
    {"scenarios", "scripts/verify-mod-scenarios.py", "typed scenario discovery and complete case receipts", "unknown cases, partial results, stale tokens and session ownership conflicts"},
    {"storage", "scripts/verify-storage-scenarios.py", "controlled array and Canvas reference observations", "incomplete cases, reference-copy rejection and retention control failures"},
    {"terrain", "scripts/verify-terrain-scenario.py", "complete ordered command payload comparison", "deliberate vertex mutation and incomplete receipts"},
    {"collection", "scripts/verify-terrain-measurement.py", "typed schedules, actual interval collection and journal import", "invalid plans and incomplete or inconsistent measurements"},
    {"ir", "tests/unit/test_ir.c", "independent bounded IR evaluation and actual PID parity", "invalid IR, unsupported shapes and deliberate semantic mutants"},
    {"pid", "scripts/verify-pid.py", "original/generated/reference PID operations and persistent state", "missing comparisons, stale source identity and semantic mismatch"},
    {"capabilities", "tests/unit/test_capabilities.c", "registry dependencies, target domains and deterministic serialization", "duplicate IDs, unknown links, cycles and invalid target claims"},
    {"doctor", "scripts/verify-doctor.py", "read-only inventory and explicit fixed C11 native probe", "missing tools, malformed metadata, failed launch, timeout and missing executable"},
    {"parser_limits", "scripts/verify-parser-limits.py", "admitted ordinary syntax and complete PID sources", "deep or oversized syntax rejects with BE0210 before recursive consumers"},
    {"analysis", "scripts/verify-analysis.py", "exact snapshot admission, byte spans and versions", "missing overlays, malformed JSON, stale hashes, held-file mutation and cancellation"},
    {"mcp", "scripts/verify-mcp.py", "CLI parity over bounded local stdio protocol", "invalid parameters, output limits, stale inputs and owned-operation cancellation"},
    {"ir_differential", "scripts/verify-ir-differential.py", "explicit bounded IR-C differential tests and retained native evidence", "unsupported shapes, wrong traps, prefix mutations and incomplete execution"},
    {"mod_plan", "scripts/verify-mod-plan.py", "deterministic v1 structural plans and real CLI/MCP parity", "malformed inputs, stale identities, resource bounds, unexpected side effects and fabricated execution/admission"},
    {"storage_admission", "scripts/verify-storage-admission.py", "admitted local scalar List operations and target copy profiles", "unsupported owning copies/transfers/returns and invalidating borrowed-storage operations"}
};

static const Feature feature_entries[] = {
    {"compiler.allocation_arithmetic", "Checked allocation arithmetic", FEATURE_BOUNDED, FEATURE_COMPILER|FEATURE_NATIVE,
     "compiler arenas/vectors and native List growth", "Checked size arithmetic and descriptor preparation in the admitted helpers; not whole-compiler memory safety or complete List cleanup.",
     "Allocation element counts and byte sizes must fit each helper's explicit representation limits.", "src/common/checked_size.h", {NULL}, {"allocation", NULL}},
    {"language.modules", "Resolved modules and declaration identity", FEATURE_BOUNDED, 7,
     "use / pub / qualified names", "Explicit imports and qualified declaration identity; generic instantiation and external extension methods remain unsupported.",
     "resolve_program and check_program", "src/sema/resolve.c", {NULL}, {"modules", NULL}},
    {"compiler.parser_limits", "Bounded per-file parser structure", FEATURE_BOUNDED, FEATURE_COMPILER | FEATURE_NATIVE | FEATURE_REFERENCE | FEATURE_ENFUSION,
     "parse_file / BE0210", "Per file: 262144 tokens including EOF, 256 guarded parser frames, AST depth 128, 262144 visited AST nodes, 1048576 charged work units. Lexing precedes this gate; no lexer allocation, cross-module/default-expansion or whole-program resource guarantee.",
     "parser token/recursion/work admission and iterative postparse AST validation", "src/parse/parser.h", {NULL}, {"parser_limits", NULL}},
    {"language.plain_values", "Plain values and parameter modes", FEATURE_BOUNDED, 7,
     "struct / fixed arrays / let / inout / set / sink", "Target admission differs. This does not establish owning-container copying, cleanup or all projected-assignment semantics.",
     "ownership_check plus selected target admission", "src/sema/ownership.c", {"language.modules", NULL}, {"values", "destinations", NULL}},
    {"language.taint", "Declared taint and authority analysis", FEATURE_PARTIAL, 7,
     "@untrusted / @secret / @server_only / @constant_time", "Bounded context-insensitive monotone propagation through record field paths, conservative indexed-element summaries, mutable arguments and call returns. This is not full symbolic validation, whole-program authority proof or a backend constant-time guarantee.",
     "taint_check", "src/sema/taint.c", {"language.modules", NULL}, {"security", NULL}},
    {"native.ast", "Ordinary native C11 lowering", FEATURE_BOUNDED, FEATURE_NATIVE,
     "beryl check / build / run / test / emit-c", "Typed AST to C11 and a selected Clang toolchain; only admitted source shapes are supported.",
     "native_lint", "src/back/c_backend.c", {"language.modules", NULL}, {"native", "driver", NULL}},
    {"native.checked_arithmetic", "Checked native arithmetic", FEATURE_BOUNDED, FEATURE_NATIVE,
     "checked integer arithmetic and explicit wrapping/saturating intrinsics", "Admitted scalar operations; this is not proof that internal container capacity arithmetic or every backend path is safe.",
     "native_lint and typed intrinsic checking", "runtime/beryl_rt.h", {"native.ast", NULL}, {"native", "traps", NULL}},
    {"native.owned_storage", "General owned storage lifecycle", FEATURE_PARTIAL, FEATURE_NATIVE,
     "List<T> and owning aggregate paths", "Local scalar/plain-element List operations remain admitted; unsupported owning copies, replacements, returns and transfer paths are rejected. General recursive copying, automatic cleanup and complete ownership/effect contracts remain unavailable.",
     "native_lint and storage_admit; incomplete general ownership profile", "src/back/c_backend.c", {"native.ast", "language.storage_admission", NULL}, {"native", "values", "storage_admission", NULL}},
    {"language.storage_admission", "Target copy and borrow containment", FEATURE_PARTIAL, FEATURE_NATIVE | FEATURE_ENFUSION,
     "storage_classify / storage_admit / BE0903 / BE0701", "Recursive resolved-type classification and bounded rejection of unsupported logical owning copies and invalidating borrows. Admitted scalar collection operations and Enfusion scalar collection-field copies do not establish general lifecycle cleanup or complete storage effects.",
     "storage_admit for the explicit target before execution jobs", "src/sema/storage.c", {"language.plain_values", NULL}, {"storage_admission", NULL}},
    {"reference.ast", "Independent bounded AST reference", FEATURE_BOUNDED, FEATURE_REFERENCE,
     "beryl test --backend reference|differential", "Explicit finite numeric/plain-record/fixed-array subset with budgets. Owning containers and conflicting projected destinations are outside coverage.",
     "reference_admit", "src/reference/admit.c", {"language.plain_values", NULL}, {"reference", "destinations", NULL}},
    {"reference.expected_traps", "Expected source-trap comparison", FEATURE_BOUNDED, FEATURE_REFERENCE | FEATURE_NATIVE,
     "beryl test --backend differential --expect-source-trap", "Overflow, division-by-zero and bounds; bounded ordered observations and optionally one admitted fixed i32 output root. Harness failures never match source traps.",
     "reference_admit and expected-trap driver validation", "src/driver/main.c", {"reference.ast", "native.ast", NULL}, {"traps", NULL}},
    {"enfusion.ast", "Ordinary EnforceScript lowering", FEATURE_BOUNDED, FEATURE_ENFUSION,
     "beryl check|build --target enfusion", "Admitted scalar/plain-record subset; selected reference-element array/list copy fields are rejected. Engine execution is separate.",
     "enfusion_lint", "src/back/enforce_backend.c", {"language.modules", NULL}, {"enfusion", "pid", NULL}},
    {"enfusion.bindings", "Exact selected engine declaration context", FEATURE_BOUNDED, FEATURE_ENFUSION | FEATURE_COMPILER,
     "beryl context binding", "35 selected local API declarations with hashes. Extracted declarations are not complete typed bindings or verified lifetime/effect/authority contracts.",
     "binding snapshot and optional engine/API identity matching", "src/driver/binding_context.c", {NULL}, {"bindings", "context", NULL}},
    {"enfusion.source_maps", "Generated-line source mappings", FEATURE_BOUNDED, FEATURE_ENFUSION,
     "beryl build --target enfusion --source-map", "Generated lines map to original byte spans; full nested expansion chains and engine-column interpolation remain unavailable.",
     "artifact/source hash and span validation", "tools/beryl-mod/source_maps.py", {"enfusion.ast", NULL}, {"maps", NULL}},
    {"mod.class_exports", "Strict companion class export profile", FEATURE_BOUNDED, FEATURE_ENFUSION | FEATURE_TOOLING,
     "beryl mod check|build|verify|promote", "Version 1 covers addon/source identity and scalar class/constructor/method exports. It does not cover complete components, resources, prefabs or layouts.",
     "strict v1 companion and export validation", "schemas/beryl.mod.v1.schema.json", {"enfusion.ast", NULL}, {"mod", "pid", NULL}},
    {"mod.scenarios", "Installed typed engine scenarios", FEATURE_BOUNDED, FEATURE_ENFUSION | FEATURE_TOOLING,
     "beryl mod scenarios / verify --scenario", "The installed tool owns exact scenario discovery and availability. Source metadata does not establish local runtime capability or a current successful receipt.",
     "installed scenario registry and artifact/session checks", "tools/beryl-mod/scenarios.py", {"mod.class_exports", NULL}, {"scenarios", "storage", "terrain", NULL}},
    {"mod.whole_authoring", "Whole-mod companion authoring", FEATURE_UNAVAILABLE, FEATURE_ENFUSION | FEATURE_TOOLING,
     "proposed companion version 2", "Components, editor properties, resources, prefab/layout/event generation and full authoring acceptance remain planned.",
     "unavailable", "docs/BERYL_ADVANCED_IMPLEMENTATION_PLAN.md", {"mod.class_exports", NULL}, {NULL}},
    {"tool.context", "Read-only semantic context", FEATURE_BOUNDED, FEATURE_COMPILER,
     "beryl context project|symbol|binding|optimization|capabilities|examples", "Uses compiler declarations and admission; does not execute programs or verify an engine session.",
     "context argument and semantic validation", "src/driver/context.c", {"language.modules", NULL}, {"context", "capabilities", NULL}},
    {"tool.doctor", "Local inventory and explicit native readiness probe", FEATURE_BOUNDED, FEATURE_COMPILER | FEATURE_TOOLING,
     "beryl doctor [--format json] [--probe native]", "Default inventory launches nothing. The explicit fixed C11 probe validates selected compile/run readiness only; Python compatibility, loaded engine sessions, complete bindings and Enfusion doctor compilation remain unverified.",
     "bounded argument, identity-file and process-outcome validation", "src/driver/doctor.c", {"tool.context", NULL}, {"doctor", NULL}},
    {"tool.native_evidence", "Retained native compilation evidence", FEATURE_BOUNDED, FEATURE_NATIVE | FEATURE_TOOLING,
     "beryl build --save-native-evidence", "Retains selected compiler identity, C, exact argv, LLVM IR and assembly when supported; dependent SDK/linker identity is incomplete. No timing result is implied.",
     "requested native compiler evidence capability", "src/driver/build.c", {"native.ast", NULL}, {"native_evidence", NULL}},
    {"tool.terrain_collection", "Exploratory terrain interval collection", FEATURE_BOUNDED, FEATURE_ENFUSION | FEATURE_TOOLING,
     "beryl mod verify --scenario measure.terrain.construction", "Typed schedules and replayable journals; same-session pairs are dependent exploratory observations, not an adoption decision or game frame-rate claim.",
     "installed measurement scenario, exact artifacts and journal validation", "tools/beryl-mod/terrain_measurements.py", {"mod.scenarios", NULL}, {"collection", "terrain", NULL}},
    {"ir.evaluator", "Experimental aggregate/PID IR evaluator", FEATURE_EXPERIMENTAL, FEATURE_COMPILER,
     "internal ir_lower / ir_verify / ir_test API", "Bounded finite f32, plain records and fixed arrays including checked dynamic projections, independent value copies and let/inout. Set/sink, owned storage and production IR remain unsupported.",
     "ir_lower and ir_verify", "src/ir/ir.c", {"reference.ast", NULL}, {"ir", NULL}},
    {"ir.codegen", "Public IR code generation", FEATURE_UNAVAILABLE, FEATURE_NATIVE | FEATURE_ENFUSION,
     "beryl build --lowering ir", "Production IR lowering returns unavailable. Auto uses AST. The separate experimental differential-test profile does not release a production backend.",
     "unavailable until whole-source-set target release", "src/driver/main.c", {"ir.evaluator", NULL}, {NULL}},
    {"ir.differential_tests", "Experimental native IR differential tests", FEATURE_EXPERIMENTAL, FEATURE_NATIVE | FEATURE_TOOLING,
     "beryl test --backend differential --lowering ir", "Instrumented schema-4 test emitter: finite binary32, i32, bool, plain records/fixed arrays and let/inout. Fixed native budgets, no owning values, production entry point, Enfusion lowering, root snapshots or performance claim. Auto remains AST.",
     "shared frontend plus whole-source-set IR admission and independent reference comparison", "src/ir/c_emit.c", {"ir.evaluator", "reference.ast", NULL}, {"ir_differential", NULL}},
    {"optimizer.released", "Released Beryl optimization families", FEATURE_UNAVAILABLE, FEATURE_NATIVE | FEATURE_ENFUSION,
     "beryl build --opt auto|off / --disable-opt", "Flags and research family discovery exist, but no automatic Beryl transformation family is released. Clang optimization flags are separate.",
     "no released plan rules", "src/driver/context.c", {"ir.codegen", NULL}, {NULL}},
    {"tool.analysis", "Exact snapshot and overlay analysis", FEATURE_BOUNDED, FEATURE_COMPILER,
     "beryl analyze --request <file>", "One-shot C analysis of all supplied bytes, with request/hash/document-version correlation and bounded strict JSON. No logical-source disk fallback, execution, persistent server or editor position conversion.",
     "strict version-1 request, identity checks and shared semantic/target passes", "src/driver/analyze.c", {"tool.context", NULL}, {"analysis", NULL}},
    {"tool.mcp", "Model-neutral local MCP adapter", FEATURE_EXPERIMENTAL, FEATURE_TOOLING,
     "beryl mcp --project <path>", "Optional installed Python stdio adapter over the same CLI. Bounded typed context, analysis, evidence, v1 structural workflow plans and explicit test/mod operations. No promotion, LSP, whole-mod planner or actual assistant trial evidence is implied.",
     "installed trusted bundle and strict protocol/tool parameters", "tools/beryl-mod/mcp_server.py", {"tool.context", "tool.analysis", NULL}, {"mcp", NULL}},
    {"tool.mod_plan", "Non-executing v1 mod workflow plans", FEATURE_BOUNDED, FEATURE_TOOLING | FEATURE_ENFUSION,
     "beryl mod plan / beryl_mod operation=plan", "Strict-v1 structural snapshot: 16 MiB per input, 64 MiB captured inputs, 3 MiB canonical plan. Symbols, target admission and engine availability remain not_checked. No compiler execution, v2/tablet or whole-mod completion.",
     "shared v1 schema/path/source-set/export-receiver validation and exact input/tool hashes", "tools/beryl-mod/mod.py", {"mod.class_exports", "mod.scenarios", NULL}, {"mod_plan", "mod", NULL}},
    {"tool.lsp", "Language server and semantic editor integration", FEATURE_UNAVAILABLE, FEATURE_TOOLING,
     "planned optional LSP adapter", "Exact unsaved snapshot analysis exists; LSP transport, editor position conversion and editor extension remain unavailable.",
     "unavailable", "docs/STATUS.md", {"tool.context", NULL}, {NULL}},
    {"library.general", "General Beryl standard library", FEATURE_UNAVAILABLE, FEATURE_NATIVE | FEATURE_ENFUSION,
     "planned tested library modules", "Compiler intrinsics exist; lib/ currently has no Beryl standard library. The SPARKOS PID is a separate tested package.",
     "unavailable", "docs/STATUS.md", {"language.modules", NULL}, {NULL}}
};

static const FeatureExample examples[] = {
    {"arithmetic.native", "Native checked arithmetic regression", FEATURE_NATIVE,
     {"tests/e2e/arith.be", NULL}, {"native.checked_arithmetic", NULL}, {"native", NULL},
     "From the repository root: beryl run tests/e2e/arith.be", "Native fixture only; this entry does not claim reference or Enfusion admission."},
    {"records.native", "Native plain-record regression", FEATURE_NATIVE,
     {"tests/e2e/structs.be", NULL}, {"native.ast", "language.plain_values", NULL}, {"native", NULL},
     "From the repository root: beryl run tests/e2e/structs.be", "Plain records; no owning-container lifecycle guarantee."},
    {"pid.complete", "Complete SPARKOS PID package", FEATURE_NATIVE | FEATURE_REFERENCE | FEATURE_ENFUSION,
     {"packages/sparkos/pid/pid.be", "packages/sparkos/pid/pid_test.be", "packages/sparkos/pid/beryl.mod.json", NULL},
     {"language.plain_values", "reference.ast", "native.ast", "mod.class_exports", NULL}, {"pid", "reference", NULL},
     "Follow packages/sparkos/pid/README.md; explicit source sets and separate native/reference and engine commands are required.",
     "Finite tested PID inputs and scalar exported interface. Historical isolated MESH candidate acceptance does not prove current source execution or dedicated multiplayer."}
};

static const OptimizationFamily families[] = {
    {"engine-map-traversal", "H01", "verified engine iteration order, complexity and invalidation"},
    {"query-fusion", "H02", "provider effects, winner identity and ordered output equivalence"},
    {"terrain-destination", "H03", "allocation, publication and engine sampling contracts"},
    {"sensor-generations", "H04", "membership identity, generation exhaustion and lifecycle contracts"},
    {"expiry-certificate", "H05", "complete mutation coverage and exact deadline comparisons"},
    {"incremental-query", "H06", "structured lowering, owned storage and accepted transition laws"},
    {"result-stability", "H07", "total non-observing guards and checked result implications"},
    {"demand-cache", "H08", "total derivations, observation roots and coherent eviction"},
    {"storage-reuse", "H09", "complete lifetime, alias and resource contracts"},
    {"loop-facts", "H10", "storage identity, effects and preservation of first failure"},
    {"checked-block", "H11", "ordered failure semantics and a private replay boundary"},
    {"private-layout", "H12", "private representation, exact conversion and measured budgets"},
    {"native-profile", "H13", "matched native workloads and reproducible compiler evidence"},
    {"checked-search", "H14", "independent legality checks and bounded offline search"}
};
#define COUNT(a) (sizeof(a) / sizeof((a)[0]))
static const FeatureRegistry registry = {feature_entries, COUNT(feature_entries), test_groups, COUNT(test_groups), examples, COUNT(examples), families, COUNT(families)};
const FeatureRegistry *features_registry(void) { return &registry; }
const char *features_state_name(FeatureState s) {
    switch (s) { case FEATURE_UNAVAILABLE: return "unavailable"; case FEATURE_EXPERIMENTAL: return "experimental";
        case FEATURE_PARTIAL: return "partial"; case FEATURE_BOUNDED: return "bounded"; }
    return "invalid";
}
uint32_t features_target(const char *name) {
    if (!name) return 0;
    return !strcmp(name,"native") ? FEATURE_NATIVE : !strcmp(name,"reference") ? FEATURE_REFERENCE :
        !strcmp(name,"enfusion") ? FEATURE_ENFUSION : !strcmp(name,"compiler") ? FEATURE_COMPILER :
        !strcmp(name,"tooling") ? FEATURE_TOOLING : 0;
}
const Feature *features_find(const FeatureRegistry *r, const char *id) {
    if (!r || !id) return NULL;
    for (size_t i=0; i<r->feature_count; i++) if (r->features[i].id && !strcmp(r->features[i].id,id)) return &r->features[i];
    return NULL;
}
const FeatureExample *features_example_find(const FeatureRegistry *r, const char *id) {
    if (!r || !id) return NULL;
    for (size_t i=0; i<r->example_count; i++) if (r->examples[i].id && !strcmp(r->examples[i].id,id)) return &r->examples[i];
    return NULL;
}
static bool present(const char *s) { return s && *s; }
static bool name_ok(const char *s, bool hyphens) {
    if (!present(s) || strlen(s)>160) return false;
    bool first=true;
    for (; *s; s++) {
        if (*s=='.') { if (first) return false; first=true; continue; }
        if (!((*s>='a' && *s<='z') || *s=='_' || (!first && *s>='0' && *s<='9') || (!first && hyphens && *s=='-'))) return false;
        first=false;
    }
    return !first;
}
static bool path_ok(const char *s) {
    return present(s) && strlen(s)<512 && *s!='/' && *s!='\\' && !strchr(s,':') && !strchr(s,'\\') && !strstr(s,"..") && !strstr(s,"//");
}
static bool issue(FeatureIssue *out, const char *kind, const char *id) {
    if (out) *out=(FeatureIssue){kind,id};
    return false;
}
static bool test_known(const FeatureRegistry *r, const char *id) {
    for (size_t i=0;i<r->test_count;i++) if (!strcmp(r->tests[i].id,id)) return true;
    return false;
}
static bool links_ok(const FeatureRegistry *r, const char *const *links, bool tests, FeatureIssue *out, const char *id) {
    for (size_t i=0;i<FEATURE_MAX_LINKS;i++) {
        if (!links[i]) return true;
        if (!(tests ? test_known(r,links[i]) : features_find(r,links[i])!=NULL)) return issue(out,tests?"unknown_test_group":"unknown_dependency",id);
        for (size_t j=0;j<i;j++) if (!strcmp(links[i],links[j])) return issue(out,"duplicate_link",id);
    }
    return issue(out,"unterminated_links",id);
}
static bool visit(const FeatureRegistry *r, size_t at, unsigned char *marks, FeatureIssue *out) {
    if (marks[at]==1) return issue(out,"dependency_cycle",r->features[at].id);
    if (marks[at]==2) return true;
    marks[at]=1;
    for (size_t i=0;r->features[at].dependencies[i];i++) {
        const Feature *dep=features_find(r,r->features[at].dependencies[i]);
        if (!visit(r,(size_t)(dep-r->features),marks,out)) return false;
    }
    marks[at]=2; return true;
}
bool features_validate(const FeatureRegistry *r, FeatureIssue *out) {
    if (out) *out=(FeatureIssue){0};
    if (!r || !r->features || !r->feature_count || r->feature_count>256 || !r->tests || !r->test_count || r->test_count>256 ||
        (r->example_count && !r->examples) || r->example_count>256 || (r->family_count && !r->families) || r->family_count>256) return issue(out,"invalid_registry",NULL);
    for (size_t i=0;i<r->test_count;i++) {
        const FeatureTestGroup *t=&r->tests[i];
        if (!name_ok(t->id,false) || !path_ok(t->source) || !present(t->positive) || !present(t->negative)) return issue(out,"invalid_test_group",t->id);
        for (size_t j=0;j<i;j++) if (!strcmp(t->id,r->tests[j].id)) return issue(out,"duplicate_test_group",t->id);
    }
    for (size_t i=0;i<r->feature_count;i++) {
        const Feature *f=&r->features[i];
        if (!name_ok(f->id,false) || !present(f->title) || !present(f->interface_name) || !present(f->bounds) || !present(f->admission) || !path_ok(f->source) ||
            f->state<FEATURE_UNAVAILABLE || f->state>FEATURE_BOUNDED || !f->targets || (f->targets&~FEATURE_ALL)) return issue(out,"invalid_feature",f->id);
        for (size_t j=0;j<i;j++) if (!strcmp(f->id,r->features[j].id)) return issue(out,"duplicate_feature",f->id);
    }
    for (size_t i=0;i<r->feature_count;i++) {
        const Feature *f=&r->features[i];
        if (!links_ok(r,f->dependencies,false,out,f->id) || !links_ok(r,f->test_groups,true,out,f->id)) return false;
        if (f->state!=FEATURE_UNAVAILABLE && !f->test_groups[0]) return issue(out,"missing_test_group",f->id);
    }
    unsigned char marks[256]={0};
    for (size_t i=0;i<r->feature_count;i++) if (!visit(r,i,marks,out)) return false;
    for (size_t i=0;i<r->example_count;i++) {
        const FeatureExample *e=&r->examples[i];
        if (!name_ok(e->id,false) || !present(e->title) || !present(e->usage) || !present(e->bounds) || !e->targets || (e->targets&~7u) || !e->features[0] || !e->test_groups[0] || !e->sources[0]) return issue(out,"invalid_example",e->id);
        for (size_t j=0;j<i;j++) if (!strcmp(e->id,r->examples[j].id)) return issue(out,"duplicate_example",e->id);
        if (!links_ok(r,e->features,false,out,e->id) || !links_ok(r,e->test_groups,true,out,e->id)) return false;
        uint32_t covered=0;
        for (size_t j=0;e->features[j];j++) {
            const Feature *f=features_find(r,e->features[j]);
            if (f->state==FEATURE_UNAVAILABLE || f->state==FEATURE_EXPERIMENTAL) return issue(out,"unavailable_example_feature",e->id);
            covered|=f->targets;
        }
        if (e->targets&~covered) return issue(out,"uncovered_example_target",e->id);
        bool ended=false;
        for (size_t j=0;j<FEATURE_MAX_LINKS;j++) { if (!e->sources[j]) { ended=true; break; } if (!path_ok(e->sources[j])) return issue(out,"invalid_example_source",e->id); }
        if (!ended) return issue(out,"unterminated_sources",e->id);
    }
    for (size_t i=0;i<r->family_count;i++) {
        const OptimizationFamily *f=&r->families[i];
        if (!name_ok(f->name,true) || !present(f->hypothesis) || strlen(f->hypothesis)!=3 || f->hypothesis[0]!='H' ||
            f->hypothesis[1]<'0' || f->hypothesis[1]>'9' || f->hypothesis[2]<'0' || f->hypothesis[2]>'9' ||
            !present(f->requires)) return issue(out,"invalid_family",f->name);
        for (size_t j=0;j<i;j++) {
            if (!strcmp(f->name,r->families[j].name)) return issue(out,"duplicate_family",f->name);
            if (!strcmp(f->hypothesis,r->families[j].hypothesis)) return issue(out,"duplicate_hypothesis",f->name);
        }
    }
    return true;
}
bool features_family_known(const char *name) {
    if (!name) return false;
    for (size_t i=0;i<registry.family_count;i++) if (!strcmp(name,registry.families[i].name)) return true;
    return false;
}
static void js(SB *b,const char *s) { json_string(b,str_from(s)); }
static void strings(SB *b,const char *const *values) {
    sb_char(b,'['); for (size_t i=0;values[i];i++) { if (i) sb_char(b,','); js(b,values[i]); } sb_char(b,']');
}
static void targets(SB *b,uint32_t bits) {
    const char *names[]={"native","reference","enfusion","compiler","tooling"}; bool first=true;
    sb_char(b,'['); for (unsigned i=0;i<5;i++) if (bits&(1u<<i)) { if (!first) sb_char(b,','); first=false; js(b,names[i]); } sb_char(b,']');
}
static void feature_json(SB *b,const Feature *f) {
    sb_cstr(b,"{\"id\":"); js(b,f->id); sb_cstr(b,",\"title\":"); js(b,f->title);
    sb_cstr(b,",\"implementation\":{\"status\":"); js(b,features_state_name(f->state)); sb_cstr(b,",\"targets\":"); targets(b,f->targets);
    sb_cstr(b,",\"interface\":"); js(b,f->interface_name); sb_cstr(b,",\"bounds\":"); js(b,f->bounds); sb_cstr(b,",\"source\":"); js(b,f->source);
    sb_cstr(b,"},\"admission\":{\"status\":\"not_checked\",\"rule\":"); js(b,f->admission);
    sb_cstr(b,",\"scope\":\"requires_actual_source_set\"},\"local_availability\":{\"status\":\"not_checked\"},\"applicable_evidence\":{\"status\":\"not_checked\",\"receipts\":[],\"reason\":\"Test links are obligations, not execution receipts; exact source/compiler/tool/engine identities require separate evidence.\"},\"dependencies\":");
    strings(b,f->dependencies); sb_cstr(b,",\"test_groups\":"); strings(b,f->test_groups); sb_char(b,'}');
}
static void example_json(SB *b,const FeatureExample *e) {
    sb_cstr(b,"{\"id\":"); js(b,e->id); sb_cstr(b,",\"title\":"); js(b,e->title); sb_cstr(b,",\"targets\":"); targets(b,e->targets);
    sb_cstr(b,",\"sources\":"); strings(b,e->sources); sb_cstr(b,",\"features\":"); strings(b,e->features);
    sb_cstr(b,",\"test_groups\":"); strings(b,e->test_groups); sb_cstr(b,",\"usage\":"); js(b,e->usage); sb_cstr(b,",\"bounds\":"); js(b,e->bounds);
    sb_cstr(b,",\"path_base\":\"Beryl_source_repository\",\"source_identity\":\"not_checked\",\"admission\":\"not_checked\",\"execution\":\"not_run\",\"applicable_evidence\":{\"status\":\"not_checked\",\"receipts\":[]}}");
}
static void test_json(SB *b,const FeatureTestGroup *t) {
    sb_cstr(b,"{\"id\":"); js(b,t->id); sb_cstr(b,",\"source\":"); js(b,t->source); sb_cstr(b,",\"positive_obligation\":"); js(b,t->positive);
    sb_cstr(b,",\"negative_obligation\":"); js(b,t->negative); sb_cstr(b,",\"execution\":\"not_run\"}");
}
Str features_families_json(Arena *a) {
    SB b; sb_init(&b,a); sb_char(&b,'[');
    for (size_t i=0;i<registry.family_count;i++) {
        const OptimizationFamily *f=&registry.families[i]; if (i) sb_char(&b,',');
        sb_cstr(&b,"{\"family\":"); js(&b,f->name); sb_cstr(&b,",\"hypothesis\":"); js(&b,f->hypothesis);
        sb_cstr(&b,",\"status\":\"proposed\",\"released\":false,\"eligible\":false,\"reason\":"); js(&b,f->requires); sb_char(&b,'}');
    }
    sb_char(&b,']'); return sb_finish(&b);
}
Str features_fingerprint(Arena *a) {
    SB b; sb_init(&b,a); sb_cstr(&b,"{\"registry_schema\":1,\"features\":[");
    for (size_t i=0;i<registry.feature_count;i++) { if (i) sb_char(&b,','); feature_json(&b,&registry.features[i]); }
    sb_cstr(&b,"],\"test_groups\":["); for (size_t i=0;i<registry.test_count;i++) { if (i) sb_char(&b,','); test_json(&b,&registry.tests[i]); }
    sb_cstr(&b,"],\"examples\":["); for (size_t i=0;i<registry.example_count;i++) { if (i) sb_char(&b,','); example_json(&b,&registry.examples[i]); }
    sb_cstr(&b,"],\"optimization_families\":"); sb_str(&b,features_families_json(a)); sb_char(&b,'}');
    return hash256_str(a,sb_finish(&b));
}
static void header(Arena *a,SB *b) {
    sb_cstr(b,"{\"schema_version\":1,\"registry_id\":\"beryl.compiler.features.v1\",\"registry_fingerprint\":"); json_string(b,features_fingerprint(a));
    sb_cstr(b,",\"scope\":\"compiled_metadata_only\",\"receipt_resolution\":\"not_implemented\"");
}
Str features_catalog_json(Arena *a,const char *id,uint32_t mask) {
    SB b; sb_init(&b,a); header(a,&b); sb_cstr(&b,",\"entries\":["); bool first=true;
    for (size_t i=0;i<registry.feature_count;i++) {
        const Feature *f=&registry.features[i]; if ((id && strcmp(id,f->id)) || !(mask&f->targets)) continue;
        if (!first) sb_char(&b,',');
        first=false; feature_json(&b,f);
    }
    sb_cstr(&b,"],\"test_groups\":["); for (size_t i=0;i<registry.test_count;i++) { if (i) sb_char(&b,','); test_json(&b,&registry.tests[i]); }
    sb_cstr(&b,"],\"released_plans\":[],\"measurements\":null}"); return sb_finish(&b);
}
Str features_examples_json(Arena *a,const char *id,uint32_t mask) {
    SB b; sb_init(&b,a); header(a,&b); sb_cstr(&b,",\"examples\":["); bool first=true;
    for (size_t i=0;i<registry.example_count;i++) {
        const FeatureExample *e=&registry.examples[i]; if ((id && strcmp(id,e->id)) || !(mask&e->targets)) continue;
        if (!first) sb_char(&b,',');
        first=false; example_json(&b,e);
    }
    sb_cstr(&b,"],\"measurements\":null}"); return sb_finish(&b);
}
