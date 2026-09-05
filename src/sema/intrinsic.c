#include "intrinsic.h"

static const struct {
    const char *name;
    Intrinsic   id;
} g_table[] = {
    {"print", INTR_PRINT},   {"println", INTR_PRINTLN}, {"assert", INTR_ASSERT},
    {"min", INTR_MIN},       {"max", INTR_MAX},         {"abs", INTR_ABS},
    {"clamp", INTR_CLAMP},   {"sqrt", INTR_SQRT},
    {"wrapping_add", INTR_WRAPPING_ADD},
    {"wrapping_sub", INTR_WRAPPING_SUB},
    {"wrapping_mul", INTR_WRAPPING_MUL},
    {"saturating_add", INTR_SATURATING_ADD},
    {"saturating_sub", INTR_SATURATING_SUB},
};

static const struct {
    const char *name;
    Intrinsic   id;
} g_list_methods[] = {
    {"len", INTR_LIST_LEN},   {"push", INTR_LIST_PUSH}, {"get", INTR_LIST_GET},
    {"set", INTR_LIST_SET},   {"clear", INTR_LIST_CLEAR},
};

static const struct {
    const char *name;
    Intrinsic   id;
} g_vec_methods[] = {
    {"length", INTR_VEC_LENGTH},         {"length_sq", INTR_VEC_LENGTH_SQ},
    {"dot", INTR_VEC_DOT},               {"distance", INTR_VEC_DISTANCE},
    {"normalized", INTR_VEC_NORMALIZED}, {"cross", INTR_VEC_CROSS},
};

Intrinsic intrinsic_list_method(Str name) {
    for (size_t i = 0; i < sizeof g_list_methods / sizeof g_list_methods[0]; i++)
        if (str_eq_c(name, g_list_methods[i].name)) return g_list_methods[i].id;
    return INTR_NONE;
}

Intrinsic intrinsic_vec_method(Str name) {
    for (size_t i = 0; i < sizeof g_vec_methods / sizeof g_vec_methods[0]; i++)
        if (str_eq_c(name, g_vec_methods[i].name)) return g_vec_methods[i].id;
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
