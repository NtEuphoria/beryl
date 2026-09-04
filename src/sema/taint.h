/* taint.h — one dataflow engine, several policies.
 *
 * The same flow-sensitive walk serves three purposes, which is what makes it
 * affordable to build at all:
 *
 *   @untrusted     values arriving from a network or RPC boundary must not
 *                  reach an index without being bounded first
 *   @secret        secret-derived values must not drive a branch or a memory
 *                  index, which is what leaks them through timing
 *   @server_only   a server-authoritative function must not be reachable from
 *                  client context
 *
 * HONESTY: this is a strong lint, not a proof. It is flow-sensitive and
 * conservative at merge points, but indirect flows through handles or computed
 * indices defeat it. docs/SECURITY.md states this as residual S3, and nothing
 * here should ever be described as making a program "safe".
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
