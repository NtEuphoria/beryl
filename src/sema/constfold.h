/* constfold.h — compile-time evaluation.
 *
 * The evaluator is a sandbox by construction rather than by policy: it
 * interprets pure expressions over integers, floats, bools and strings, and
 * there is no file, network, environment or clock access to disable because
 * none of it is implemented. It is bounded in steps so that a non-terminating
 * constant is a diagnostic rather than a hang.
 */
#ifndef BERYL_CONSTFOLD_H
#define BERYL_CONSTFOLD_H

#include "../common/diag.h"
#include "resolve.h"

typedef enum { CV_NONE = 0, CV_INT, CV_FLOAT, CV_BOOL, CV_STR, CV_UINT } ConstKind;

typedef struct {
    ConstKind kind;
    int64_t   i;
    double    f;
    bool      b;
    Str       s;
    uint64_t  u; /* CV_UINT retains the complete unsigned magnitude */
} ConstVal;

/* Evaluates `e`. When `report` is false, failure is silent, which is what
 * callers that are merely *asking* whether something is constant want. */
ConstVal const_eval(Arena *a, DiagBag *d, Program *p, Expr *e, bool report);

/* Convenience for array lengths: reports BE0505 unless `e` is a constant
 * non-negative integer. */
bool const_eval_len(Arena *a, DiagBag *d, Program *p, Expr *e, uint64_t *out);
bool const_eval_len_in(Arena *a, DiagBag *d, Program *p, Module *module, Item *scope,
                       Expr *e, uint64_t *out);

#endif /* BERYL_CONSTFOLD_H */
