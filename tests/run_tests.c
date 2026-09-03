/* Test registry. Each suite exposes a single run_*_tests() entry point. */
#include "unit/test.h"

void run_common_tests(void);
void run_diag_tests(void);

int main(void) {
    run_common_tests();
    run_diag_tests();
    return t_summary();
}
