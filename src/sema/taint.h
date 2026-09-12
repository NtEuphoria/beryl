/* taint.h — one dataflow engine, several policies.
 *
 * A bounded monotone whole-program analysis serves three source policies:
 *
 *   @untrusted     values arriving from a network or RPC boundary must not
 *                  reach an index without being bounded first
 *   @secret        secret-derived values must not drive a branch or a memory
 *                  index, which is what leaks them through timing
 *   @server_only   a server-authoritative function must not be reachable from
 *                  client context
 *
 * Record fields retain separate local provenance; indexed elements use a
 * conservative summary. Calls, returned sources and mutable arguments propagate
 * to a fixed point before diagnostics. Fixed-array integer bounds are separate
 * facts, never universal removal of provenance. The initial call analysis is
 * context-insensitive; symbolic summaries and dynamic-storage facts remain
 * incomplete. Exhaustion fails explicitly with BE0608. This is not a claim of
 * complete memory safety, runtime server authority or machine constant time.
 */
#ifndef BERYL_TAINT_H
#define BERYL_TAINT_H

#include "../common/diag.h"
#include "resolve.h"

typedef enum {
    TAINT_NONE      = 0,
    TAINT_UNTRUSTED = 1u << 0,
    TAINT_SECRET    = 1u << 1,
} TaintKind;

typedef struct {
    /* From `[security] forbid_unsafe` in beryl.toml. */
    bool forbid_unsafe;
} SecurityOpts;

bool taint_check(DiagBag *d, Program *p, SecurityOpts o);

/* Attribute lookup shared with the audit report and the Enfusion backend. */
bool item_has_attr(const Item *it, const char *name);
Str  item_attr_arg(const Item *it, const char *name);

#endif /* BERYL_TAINT_H */
