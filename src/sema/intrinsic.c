#include "intrinsic.h"

static const struct {
    const char *name;
    Intrinsic   id;
} g_table[] = {
    {"print", INTR_PRINT},   {"println", INTR_PRINTLN}, {"assert", INTR_ASSERT},
    {"min", INTR_MIN},       {"max", INTR_MAX},         {"abs", INTR_ABS},
    {"clamp", INTR_CLAMP},   {"sqrt", INTR_SQRT},
};

static const struct {
    const char *name;
    Intrinsic   id;
} g_list_methods[] = {
    {"len", INTR_LIST_LEN},   {"push", INTR_LIST_PUSH}, {"get", INTR_LIST_GET},
    {"set", INTR_LIST_SET},   {"clear", INTR_LIST_CLEAR},
};

Intrinsic intrinsic_list_method(Str name) {
    for (size_t i = 0; i < sizeof g_list_methods / sizeof g_list_methods[0]; i++)
        if (str_eq_c(name, g_list_methods[i].name)) return g_list_methods[i].id;
    return INTR_NONE;
}

Intrinsic intrinsic_from_name(Str name) {
    for (size_t i = 0; i < sizeof g_table / sizeof g_table[0]; i++)
        if (str_eq_c(name, g_table[i].name)) return g_table[i].id;
    return INTR_NONE;
}

const char *intrinsic_name(Intrinsic i) {
    for (size_t k = 0; k < sizeof g_table / sizeof g_table[0]; k++)
        if (g_table[k].id == i) return g_table[k].name;
    return "?";
}
