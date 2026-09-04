/* audit.c — reports a package's declared security surface.
 *
 * This is a declaration-level report, deliberately. It says what the code
 * asks for, not what it is guaranteed to do, and the footer says so in those
 * words. The word "safe" does not appear in the output.
 */
#include "audit.h"

#include <stdio.h>

#include "../sema/taint.h"

typedef struct {
    const char *name;
    const char *what;
    uint32_t    count;
} AttrRow;

static void print_unsafe_uses(Program *p, SourceMap *sm, uint32_t *total);

static void scan_unsafe_expr(Expr *e, SourceMap *sm, Item *owner, uint32_t *total) {
    if (!e) return;
    switch (e->kind) {
        case EX_UNSAFE: {
            LineCol     lc = srcmap_linecol(sm, e->span);
            SourceFile *f  = srcmap_get(sm, e->span.file);
            printf("  %-18.*s %.*s:%u  in `%.*s`\n",
                   (int)e->unsafe_expr.capability.len, e->unsafe_expr.capability.ptr,
                   f ? (int)f->path.len : 0, f ? f->path.ptr : "", lc.line,
                   (int)owner->name.len, owner->name.ptr);
            (*total)++;
            scan_unsafe_expr(e->unsafe_expr.body, sm, owner, total);
            break;
        }
        case EX_BLOCK:
            for (uint32_t i = 0; i < e->block.stmts.len; i++) {
                Stmt *s = e->block.stmts.data[i];
                if (!s) continue;
                switch (s->kind) {
                    case ST_LET: scan_unsafe_expr(s->let.init, sm, owner, total); break;
                    case ST_EXPR:
                    case ST_RETURN:
                    case ST_DEFER: scan_unsafe_expr(s->expr, sm, owner, total); break;
                    case ST_ASSIGN:
                        scan_unsafe_expr(s->assign.value, sm, owner, total);
                        break;
                    case ST_WHILE:
                        scan_unsafe_expr(s->while_st.cond, sm, owner, total);
                        scan_unsafe_expr(s->while_st.body, sm, owner, total);
                        break;
                    case ST_FOR: scan_unsafe_expr(s->for_st.body, sm, owner, total); break;
                    default: break;
                }
            }
            break;
        case EX_IF:
            scan_unsafe_expr(e->if_expr.then_blk, sm, owner, total);
            scan_unsafe_expr(e->if_expr.else_blk, sm, owner, total);
            break;
        default: break;
    }
}

static void print_unsafe_uses(Program *p, SourceMap *sm, uint32_t *total) {
    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (item_has_attr(it, "unsafe")) {
                LineCol     lc = srcmap_linecol(sm, it->span);
                SourceFile *f  = srcmap_get(sm, it->span.file);
                Str         a  = item_attr_arg(it, "unsafe");
                printf("  %-18.*s %.*s:%u  on `%.*s`\n", (int)a.len,
                       str_empty(a) ? "(unspecified)" : a.ptr, f ? (int)f->path.len : 0,
                       f ? f->path.ptr : "", lc.line, (int)it->name.len, it->name.ptr);
                (*total)++;
            }
            if (it->kind == IT_FN && it->fn.body)
                scan_unsafe_expr(it->fn.body, sm, it, total);
            else if (it->kind == IT_TEST && it->test.body)
                scan_unsafe_expr(it->test.body, sm, it, total);
        }
    }
}

int audit_report(Program *p, SourceMap *sm, Str package_name, bool forbid_unsafe) {
    printf("beryl audit");
    if (!str_empty(package_name)) printf("  %.*s", (int)package_name.len, package_name.ptr);
    printf("\n\n");

    printf("unsafe surface\n");
    uint32_t unsafe_total = 0;
    print_unsafe_uses(p, sm, &unsafe_total);
    if (unsafe_total == 0) printf("  (none)\n");
    printf("  forbid_unsafe = %s\n", forbid_unsafe ? "true" : "false");
    printf("\n");

    AttrRow rows[] = {
        {"untrusted", "parameters treated as attacker-controlled", 0},
        {"validator", "launders untrusted values", 0},
        {"secret", "parameters treated as secret", 0},
        {"constant_time", "no secret-dependent branch or index", 0},
        {"server_only", "not reachable from client context", 0},
    };
    uint32_t nrows = sizeof rows / sizeof rows[0];

    uint32_t fns = 0;
    for (uint32_t m = 0; m < p->modules.len; m++) {
        Module *mod = p->modules.data[m];
        for (uint32_t i = 0; i < mod->items.len; i++) {
            Item *it = mod->items.data[i];
            if (it->kind != IT_FN) continue;
            fns++;
            for (uint32_t r = 0; r < nrows; r++)
                if (item_has_attr(it, rows[r].name)) rows[r].count++;
        }
    }

    printf("security attributes  (%u function%s in this package)\n", fns,
           fns == 1 ? "" : "s");
    bool any_attr = false;
    for (uint32_t r = 0; r < nrows; r++) {
        if (!rows[r].count) continue;
        any_attr = true;
        printf("  @%-16s %2u   %s\n", rows[r].name, rows[r].count, rows[r].what);
    }
    if (!any_attr) printf("  (none declared)\n");
    printf("\n");

    printf("build-time code execution\n");
    printf("  none, by construction: Beryl has no build scripts and no procedural\n");
    printf("  macros, and comptime evaluation implements no I/O to disable\n");
    printf("\n");

    printf("what this report is\n");
    printf("  A record of what the code DECLARES, not a proof of what it does.\n");
    printf("  The taint analysis behind @untrusted and @secret is flow-sensitive\n");
    printf("  and conservative, but indirect flows through handles or computed\n");
    printf("  indices defeat it. Capabilities bind what compiled Beryl code can\n");
    printf("  express, not what machine code can do: one @unsafe(ffi) block leaves\n");
    printf("  the model entirely. See docs/THREAT-MODEL.md, residuals S2 and S3.\n");

    return 0;
}
