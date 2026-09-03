/* Test registry. Each suite exposes a single run_*_tests() entry point. */
#include "unit/test.h"

void run_common_tests(void);
void run_diag_tests(void);
void run_lexer_tests(void);
void run_parser_tests(void);
void run_sema_tests(void);

int main(void) {
    run_common_tests();
    run_diag_tests();
    run_lexer_tests();
    run_parser_tests();
    run_sema_tests();
    return t_summary();
}
