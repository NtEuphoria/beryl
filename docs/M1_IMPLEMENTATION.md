# M1 implementation packet: declaration identity

Status: implemented and verified for the bounded contracts below. Governing plan:
[SPARKOS_IMPLEMENTATION_PLAN.md](SPARKOS_IMPLEMENTATION_PLAN.md).

## Objective and dependency gate

Make module boundaries and generated identifiers reliable enough for one PID
implementation imported by tests and emitted for both targets. M0's Windows
native execution gates are the prerequisite. No lifetime syntax or ownership
semantic change is part of this packet.

## Starting evidence (before M1 changes)

- Program.shorts selects the first item with a spelling across every module.
- Resolver creates named types using short names; type interning uses their text.
- Methods use `Recv.method` where Recv is an unqualified spelling.
- Unknown one/two-character types are treated as generic parameters.
- Qualified calls can fall back to an unrelated global short name.
- Const evaluation has its own short-name fallback, including before array extent
  checking; fixing only ordinary expression lookup would leave a second bug.
- Native mangling replaces punctuation with underscores. Enfusion types and
  free-function holders also lose namespace information; keyword escaping can
  collide with already-suffixed source names.
- Multiple source files may declare one module; scope and emitted holders must
  account for every file, not just the last Module pointer in an index.
- Existing pid_test.be repeats PID implementation instead of importing pid.be.

## Intended contracts

1. A logical module is identified by its full dotted path and can span source
   files. Its items and imports form a deterministic scope.
2. Unqualified lookup considers lexical locals, current-module declarations,
   explicit item imports, then applicable built-ins. Never use a program-global
   first-name-wins fallback.
3. `use package.module.Item` imports an item. `use package.module` introduces the
   module's last segment for qualified lookup. Full qualified references must
   resolve to real declarations and honor visibility.
4. Unknown imports fail. Conflicting imports/declarations report both sites.
   Repeating the same import is harmless; importing different declarations under
   one name is ambiguous. Explicit `use` dependency cycles remain errors.
   Fully qualified references do not currently add implicit import-graph edges.
5. Item-level `pub` applies across logical module boundaries, including methods.
   Current record fields remain part of the accessible record value contract;
   new field-privacy syntax is outside this packet.
6. A named type's interned identity includes its declaration's qualified identity.
   Generic parameters exist only in a declaring generic item's scope, with their
   own declaration identity. Instantiation remains a separately unsupported feature.
7. Receiver declarations determine method identity. Initially, methods are defined
   in their receiver's module; external extension-method policy is not inferred.
8. Constant initializer lookup belongs to the constant's declaration module, not
   to the first caller's locals/imports. Array extent evaluation has explicit scope.
9. Generated identifiers use injective encoding and separate categories for
   items/types/fields/methods/helpers/temporaries. Internal names cannot collide
   with runtime identifiers or engine helper names. Repeated same-module source
   files produce one free-function holder.
10. Engine-facing stable exports require explicit mappings. The PID export packet
    supplies those mappings; internal naming does not silently preserve accidental
    public API spelling from the old backend.

## Affected files and consumers

Resolver/type interning; checker ordinary/qualified calls and literals; constfold
pre-check extent evaluation; AST resolved receiver/import metadata; both backend
identifier/type/field/method/holder emission; unit tests; multi-file integration
fixtures; PID examples; CLI documentation and support status.

The native test default remains native. Reference execution waits for M2.

## Required positive and negative tests

- Same-spelled public records and methods in distinct modules stay distinct.
- Passing one module's record where another is required fails type checking.
- Lexical shadowing takes precedence; an unrelated module cannot shadow built-ins.
- Explicit item/module imports and multi-segment qualified calls/constants/types work.
- Missing import, ambiguous import, private function/type/method access fail.
- Unknown short and long type names fail; only declared generic parameters resolve.
- Same logical module across files resolves all items and emits one holder.
- Imported constants and array extents evaluate in declaration scope.
- Punctuation/underscore naming collisions, target keywords, helper-like names,
  and duplicate test labels in separate files cannot collide in generated output.
- Generated C and EnforceScript deterministic across repeated identical builds.
- Real native multi-module execution and actual Workbench compilation of emitted
  regression function bodies. A main-only fixture is not engine evidence.
- Existing foundation/driver regressions stay green after compatibility updates.

## Migration and completion evidence

Update examples to import implementation explicitly. Update tests that previously
depended on accidental global visibility or short generated names, with behavior
checks for their replacements. Preserve generated public names only through the
explicit export mechanism. Do not edit live MESH while resolving module semantics.

Mark completed only with exact source/compiler hashes, positive/negative outcomes,
both target naming checks, and documented remaining export limitations. M2/M3
must not proceed on an unverified global-lookup workaround.

## Implementation checkpoint

The resolver now coalesces files into logical module scopes and implements
item/module imports, visibility, declaration-qualified types and methods, and
declared generic parameter identity. Constant evaluation and array extents use
their declaration context. Both emitters encode internal symbols injectively;
Enfusion emits one holder across files in the same module. Native entry-point
ambiguity and invalid Enfusion output prefixes fail with diagnostics.

The PID example test module imports `flight.pid.Pid`. Its previous private copy
had integral clamping absent from pid.be; the shared example now includes that
clamp. It remains an incomplete example, not the complete MESH controller port.

`tests/modules/*.be` exercises duplicate type/method spellings, punctuation-like
names, static methods, helper-like method names, multiple same-module files,
private constants, imported extents, and lexical names that resemble temporaries.
Its ordinary `exercise` function remains in Enfusion output for real compilation.
Foundation verification executes its native program and four test blocks at O0/O2.

Explicit class/method export mappings are implemented as low-level compiler flags
`--export-class qualified.Type=EngineClass` and
`--export-method qualified.Type.method=EngineMethod`. They require public,
concrete declarations and reject conflicting or reserved names. Initial exported
arguments are read-only scalar bool/i32/f32 values; results are scalar or void.
Defaults are scalar literals, and a self receiver is let/inout. Constructor
mappings and strict companion JSON orchestration remain M3 work.

Core M1 evidence: build/foundation-q8hxz5o4/results.json (292 cases / 1,219 checks;
15 native O0/O2 programs; shared PID tests), driver & spaces-tmlp5n1m/results.json
(all CLI gate groups), and enfusion-proof-b2eaf5d5061e42f2aa697e141149d47b/result.json
(real Workbench compile). The export additions require fresh validation before
the milestone checkpoint is published. Failed development runs are retained;
foundation-ss7iapd2 failed only because the duplicate-parameter regression expected
a semantic diagnostic although the parser already rejects it with BE0205.

Final exported-interface validation passed:

- build/foundation-vblu_i1j/results.json: 295 cases / 1,235 checks; all 15
  native O0/O2 programs; shared PID tests; deterministic exports and CLI failures.
- build/foundation-tg0wxlnk/results.json: complete UBSan run passed.
- build/driver & spaces-e8x7l2cd/results.json: all execution-driver gates passed.
- build/enfusion-proof-28cd13808d98483ba0792769a435511f/result.json: Workbench
  compiled the ordinary multi-module bodies with explicit class/method exports,
  exit 0 and no warnings/errors. This is compilation, not runtime validation.
- build/foundation-vblu_i1j/publication.json: installed compiler hash
  c9b5fb853096d5510bc74e779a7d1209af600c9e604ff5a6ceaf14f342c3d86e;
  previous verified M0 binary preserved for rollback.

Constructor mappings and companion JSON are explicit M3 follow-on work, not
claimed here. The generated ABI changed intentionally; use export mappings for
engine-facing names and regenerate output. Existing native CLI commands remain
compatible. Generic instantiation and general owned values remain outside M1.
