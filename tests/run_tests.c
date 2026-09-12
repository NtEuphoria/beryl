/* Test registry. Each suite exposes a single run_*_tests() entry point. */
#include "unit/test.h"
#include <string.h>

void run_common_tests(void);
void run_diag_tests(void);
void run_lexer_tests(void);
void run_parser_tests(void);
void run_sema_tests(void);
void run_ownership_tests(void);
void run_enfusion_tests(void);
void run_security_tests(void);
void run_driver_tests(const char *self);
void run_module_tests(void);
void run_reference_tests(void);
void run_ir_tests(void);
void run_ir_c_tests(void);
void run_allocation_tests(void);
void run_destination_tests(void);
void run_capability_tests(void);
void run_storage_admission_tests(void);
void run_parser_limits_tests(void);
void run_json_read_tests(void);
void run_analyze_tests(void);
int driver_child(int argc, char **argv);

int main(int argc, char **argv) {
    if (argc > 1 && !strcmp(argv[1], "--driver-child")) return driver_child(argc, argv);
    run_common_tests();
    run_allocation_tests();
    run_diag_tests();
    run_lexer_tests();
    run_parser_tests();
    run_parser_limits_tests();
    run_sema_tests();
    run_ownership_tests();
    run_destination_tests();
    run_storage_admission_tests();
    run_enfusion_tests();
    run_security_tests();
    run_driver_tests(argv[0]);
    run_module_tests();
    run_reference_tests();
    run_ir_tests();
    run_ir_c_tests();
    run_capability_tests();
    run_json_read_tests();
    run_analyze_tests();
    return t_summary();
}
