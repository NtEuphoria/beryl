/* test.h — the whole test framework. Deliberately tiny: a compiler with zero
 * dependencies should not acquire one just to run its own tests. */
#ifndef BERYL_TEST_H
#define BERYL_TEST_H

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#include "../../src/common/str.h"

extern int t_checks;
extern int t_fails;
extern int t_cases;

void t_case(const char *name);
void t_check_(bool ok, const char *expr, const char *file, int line);
void t_check_eq_i_(long long a, long long b, const char *ea, const char *eb,
                   const char *file, int line);
void t_check_eq_s_(Str a, const char *b, const char *ea, const char *file, int line);
void t_check_contains_(Str hay, const char *needle, const char *ea, const char *file,
                       int line);
int  t_summary(void);

#define CASE(name)          t_case(name)
#define CHECK(cond)         t_check_((cond), #cond, __FILE__, __LINE__)
#define CHECK_EQ_I(a, b)    t_check_eq_i_((long long)(a), (long long)(b), #a, #b, __FILE__, __LINE__)
#define CHECK_EQ_S(a, b)    t_check_eq_s_((a), (b), #a, __FILE__, __LINE__)
#define CHECK_CONTAINS(h, n) t_check_contains_((h), (n), #h, __FILE__, __LINE__)

#endif /* BERYL_TEST_H */
