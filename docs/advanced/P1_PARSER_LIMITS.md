# P1 bounded parser and syntax-tree admission

Status: implementation and independent source review complete; focused unit
and CLI checks passed. The integrated immutable compiler gate remains a
separate release requirement.

## Problem and implemented boundary

The parser previously had no explicit depth limit for nested expressions,
types, blocks, or direct `else if` recursion. Its iterative Pratt/postfix loops
could also construct a deeply nested syntax tree without deeply nesting the
parser itself. Such a tree then reached recursive printers and semantic passes.
The parameter duplicate-name scan could perform quadratic work on a very wide
signature without a work budget.

This checkpoint introduces per-file parser admission with BE0210. It preserves
the existing language semantics and ordinary AST backend. It does not expose a
limit bypass flag or release IR lowering.

## Exact limits

The constants are published in `src/parse/parser.h`.

| Constant | Current value | What is counted |
| --- | ---: | --- |
| `PARSE_MAX_TOKENS` | 262,144 | Token records supplied to one `parse_file` call, including final EOF. |
| `PARSE_MAX_RECURSION` | 256 | Active guarded parser entries, not a count of every C helper stack frame. |
| `PARSE_MAX_AST_DEPTH` | 128 | Parsed item root at depth one; each Expr, Stmt, TypeExpr, or nested Item child adds one. |
| `PARSE_MAX_AST_NODES` | 262,144 | Non-null nodes submitted to the final syntax-shape walk. |
| `PARSE_MAX_WORK` | 1,048,576 | Token-consumption calls, guarded parser entries, parameter-name comparisons, and final shape-walk visits. |

Recursion guards cover `parse_expr`, Pratt `parse_bin`, unary parsing, type
parsing, block parsing, and direct `parse_if` recursion. Parentheses, nested
generic/error-union/array types, array length expressions, block expressions,
and `else if` chains therefore cross a guard before recursively repeating.

The final syntax-shape walk is iterative. It traverses:

- Every expression child, including call callee/arguments, array elements,
  casts, struct literal types/fields, all control-flow arms, and path type args.
- Every statement child, including declared types, assignment destinations,
  initializers, loop expressions/bodies, return and immediate-defer expressions.
- Type elements, generic type arguments, and array length expressions.
- Function return types, parameter types/defaults, bodies, struct field
  types/defaults, enum discriminants, constants, tests, and trait methods.

Generic parameter bounds, attributes, names, and path segments in the current
AST contain scalar/string metadata rather than additional recursive nodes.
New AST variants must extend this walk before being advertised as supported.

This post-parse boundary catches flat left-associative operators, field/call/
index/cast chains, and repeated optional-type suffixes. Parsing those chains
iteratively does not exempt the resulting tree from the depth limit.

## Error and recovery contract

`parse_file` validates token-vector metadata before its first lookup: nonempty
storage, length within capacity, valid token kinds, and exactly one EOF at the
end. An over-limit token count is rejected before looking through the supplied
vector. Malformed token metadata is an internal API error reported with BE0210;
it is not presented as a user grammar error.

Resource exhaustion reports the specific counted resource and its limit, adds
repair guidance, and exits the active `parse_file` through a scoped
`setjmp`/`longjmp` recovery boundary. This is compiler error recovery, not Beryl
source-language unwinding. It stops cascading syntax recovery at a position
that has already exhausted the budget.

The returned module has zero items. A partial deep AST is never published to
the printer or semantic consumers. The BE0210 diagnostic remains in the caller's
diagnostic bag, so returning a module does not imply successful parsing. Module
identity/metadata may remain; the source tree's items are discarded logically.
Arena allocations are released at the caller's existing arena lifetime.

The nonlocal recovery arm only accesses the module pointer initialized before
`setjmp` and never reassigned afterward, plus that pointer's heap storage. It
does not inspect modified automatic parser state after `longjmp`.

`parse_expr`, `parse_type`, and the other `P` helpers are internal APIs used
under an active `parse_file` boundary. They are not standalone entry points for
an arbitrarily initialized `P` object.

## Compatibility and scope

Ordinary functions, records, defaults, loops, and the current full SPARKOS PID
implementation remain admitted. The exact AST depth boundary is tested: a
function return expression with 124 left-associative additions reaches depth
128 and succeeds; one more addition is rejected. Thirty-two nested parentheses
around an ordinary arithmetic expression also succeed.

Large generated expressions/signatures must be split into smaller expressions
or functions; oversized files can be split into modules. This checkpoint does
not rewrite expressions, reassociate arithmetic, change evaluation order, or
silently skip unsupported syntax.

These are structural budgets, not a wall-clock guarantee. Work units do not
measure the byte cost of every string comparison. Limits are currently per
file, not a combined project budget.

Lexing has already produced the token vector when `parse_file` is called.
Consequently the token limit bounds parser admission and subsequent syntax
construction; it does **not** bound lexer token allocation. Ordinary filesystem
reads currently cap one source at 64 MiB, but that is not a universal source API
or total project bound. Lexical allocation, cross-module work, default expansion,
monomorphization, semantic type-graph depth, and total compiler memory remain
separate resource-safety gates.

## Verification

Persistent regression sources:

```text
tests/unit/test_parser_limits.c
scripts/verify-parser-limits.py
```

The unit registry entry point is `run_parser_limits_tests()`. The unit suite
includes existing parser tests, malformed token vectors, an oversized vector
whose real storage is deliberately tiny, exact AST-depth boundaries, ordinary
nesting, and the actual current PID implementation and test files.

Focused units pass at O0 and O2 with UBSan and first-error termination:
**56 cases, 218 checks per build**.

The CLI harness accepts `--beryl`, optional `--source-root`, and optional
`--output-root`. It copies and hashes the candidate compiler, retains generated
fixtures and raw command results, uses explicit timeouts, and records startup
failure, timeout, and cancellation as non-success. It never treats an arbitrary
nonzero exit as evidence that a limit worked: each negative fixture must return
exit one and the expected BE0210 resource category.

Fifteen adversarial shapes are exercised through **both `check` and `ast`**:
parentheses, unary nesting, generic types, array types, error unions, optional
chains, else-if chains, blocks, flat binary operators, fields, calls, indices,
casts, excessive parameter-comparison work, and an actual source whose token
count exceeds the limit. The AST route additionally checks that rejection did
not expose a large partial syntax tree.

The positive CLI gate type-checks ordinary nested arithmetic and the complete
PID implementation/test sources, then runs the PID reference corpus:
**8 tests and 2,206 assertions**. These sources are copied with before/after
hash checks; the harness records the exact bytes used.

Completed focused evidence:

```text
build/p1-parser-7icq_pg3/results.json
build/p1-parser-7icq_pg3/parser-limits-kp8ebxcg/results.json
```

The final wrapper and nested CLI report both pass. The compiler SHA-256 is:

```text
771f8e1f82090ae2aa92b5926b7c975564de22904cd5f8faa5ed7f50abc28587
```

This focused build uses the recorded delivery baseline plus explicit allocation
and parser overlays. It takes the previously tested P1 C backend from its saved
snapshot, so concurrent storage-admission edits cannot create a mixed capture.
The report records every source hash and each overlay's origin. It is not a
claim that the full live working tree has passed integration.

Earlier retained evidence includes `build/p1-parser-82j28epe/results.json`, whose
overall wrapper failed on a test-only positive fixture that returned an integer
without declaring a return type. That fixture was corrected, its unchanged
compiler passed `build/parser-limits-xyybzco2/results.json`, and the final clean
run above passed. The correction did not change compiler semantics.

Independent read-only review found no missing current AST edge, unguarded
recursive parser cycle, or use of modified automatic state after the nonlocal
resource exit. Sanitizer and execution evidence is for the tested Windows x64
Clang environment; it is not a universal proof about every host stack size.

## Integration requirements

1. Register `run_parser_limits_tests()` and document BE0210 in the diagnostic
   inventory.
2. Run the full immutable foundation and UBSan suites with the concurrent
   ownership, storage-admission, taint, allocator, and tooling work integrated.
3. Include `scripts/verify-parser-limits.py` alongside the allocator failure
   harness in compiler checkpoint verification.
4. Keep lexer admission and later semantic expansion budgets visible as
   remaining work; do not label this bounded parser checkpoint complete
   whole-compiler resource safety.
