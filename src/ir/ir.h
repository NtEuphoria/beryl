/* Experimental structured IR. Only explicit bounded native differential tests
 * select IR emission; production builds and automatic lowering remain AST.
 * Every relationship is an index into an arena-owned table. AST pointers are
 * used only during lowering; the resulting program can outlive the AST arena. */
#ifndef BERYL_IR_H
#define BERYL_IR_H
#include "../common/diag.h"
#include "../common/vec.h"
#include <stdio.h>

typedef struct Program Program;
#define IR_NONE UINT32_MAX
#define IR_MAX_FUNCTIONS 256u
#define IR_MAX_PLACES 8192u
#define IR_MAX_VALUES 16384u
#define IR_MAX_INSTRUCTIONS 16384u
#define IR_MAX_REGIONS 4096u
#define IR_MAX_ARGUMENTS 32768u
#define IR_MAX_DEPTH 128u
#define IR_MAX_CALL_ARGUMENTS 256u
#define IR_MAX_SOURCE_FILES 256u
#define IR_MAX_SOURCE_BYTES (32u * 1024u * 1024u)

typedef uint32_t IrType;
enum { IR_VOID, IR_BOOL, IR_I32, IR_F32, IR_FIRST_AGGREGATE };
#define IR_MAX_TYPES 256u
#define IR_MAX_FIELDS 2048u
#define IR_MAX_CELLS 256u
typedef enum { IR_LET, IR_INOUT } IrMode;
typedef struct { IrType type; Str identity; Span declaration; uint32_t offset; } IrField;
typedef enum { IR_TYPE_RECORD, IR_TYPE_ARRAY } IrAggregateKind;
typedef struct {
    IrAggregateKind kind;
    Str identity; Span declaration;
    uint32_t fields_start, fields_count, cells;
    IrType element;
    uint32_t length; /* logical length, independent of empty-array storage padding */
} IrAggregate;
typedef enum { IR_REGION_BODY, IR_REGION_BRANCH, IR_REGION_CONDITION, IR_REGION_STEP } IrRegionKind;
typedef enum {
    IR_CONST, IR_LOAD, IR_INIT, IR_STORE, IR_UNARY, IR_BINARY, IR_CALL,
    IR_IF, IR_LOOP, IR_RETURN, IR_BREAK, IR_CONTINUE, IR_YIELD, IR_PRINT, IR_ASSERT,
    IR_CAST, IR_INTRINSIC, IR_RECORD, IR_FIELD, IR_CAPTURE, IR_DESTINATION,
    IR_ARRAY, IR_INDEX_VALUE, IR_INDEX_BASE, IR_INDEX_PLACE
} IrOp;
typedef enum {
    IR_NEG, IR_NOT, IR_BIT_NOT, IR_ADD, IR_SUB, IR_MUL, IR_DIV, IR_REM,
    IR_BIT_AND, IR_BIT_OR, IR_BIT_XOR, IR_EQ, IR_NE, IR_LT, IR_LE, IR_GT, IR_GE, IR_SHL, IR_SHR
} IrNumeric;
typedef enum { IR_MIN, IR_MAX, IR_ABS, IR_CLAMP, IR_WRAP_ADD, IR_WRAP_SUB,
    IR_WRAP_MUL, IR_SAT_ADD, IR_SAT_SUB } IrIntrinsic;
enum { IR_READ=1u, IR_WRITE=2u, IR_FAILURE=4u, IR_OBSERVE=8u, IR_EXIT=16u, IR_ALL_EFFECTS=31u };
typedef struct { Span origin; bool has_expansion; Span expansion; bool synthetic; } IrSource;
typedef struct {
    IrType type;
    uint32_t function, definition;
} IrValue;
typedef struct {
    IrType type;
    uint32_t function, source_local;
    Span declaration;
    bool parameter, mutable, synthetic;
    IrMode mode;
    uint32_t parent, field; /* IR_NONE for roots; exact indexed record field for static projections */
    uint32_t definition; /* dynamic index instruction, otherwise IR_NONE */
} IrPlace;
typedef struct {
    IrOp op;
    IrNumeric numeric;
    IrIntrinsic intrinsic;
    IrSource source;
    uint32_t region, next, result, effects;
    uint32_t a, b, place, function, args_start, args_count;
    uint32_t child[3]; /* IF: then/else; LOOP: condition/body/step */
    int32_t immediate;
    uint32_t float_bits;
    bool flag; /* PRINT newline */
} IrInstruction;
typedef struct {
    uint32_t function, parent_instruction, first, last;
    IrRegionKind kind;
    Span source;
} IrRegion;
typedef struct {
    Str identity;
    Span declaration;
    IrType result;
    bool test;
    uint32_t body, places_start, places_count, values_start, values_count, parameters;
} IrFunction;
typedef struct { uint32_t value; Span source; bool by_place; IrMode mode; uint32_t capture, field; } IrArgument;
typedef struct { Str path, text, sha256; } IrSourceFile;
typedef struct {
    uint32_t schema_version;
    VEC(IrSourceFile) sources;
    Str source_manifest_sha256;
    VEC(IrAggregate) aggregates;
    VEC(IrField) fields;
    VEC(IrFunction) functions;
    VEC(IrPlace) places;
    VEC(IrValue) values;
    VEC(IrInstruction) instructions;
    VEC(IrRegion) regions;
    VEC(IrArgument) arguments;
} IrProgram;
typedef struct { bool ok; Span source; const char *reason; } IrVerification;

/* Requires an already resolved, checked and ownership-checked Program.
 * Admission emits BE1101; an internally invalid lowered program emits BE1102.
 * Admits void/bool/i32/finite-f32, initialized plain record values, static
 * record field projections, let/inout parameters, expanded defaults and
 * concrete functions/methods. Captured sources, types and fields own their
 * identities; projected destinations reject overlapping RHS mutation.
 * Fixed arrays preserve value copies and iteration snapshots; dynamic index
 * places require explicit bounds checks and stable access intervals.
 * Uninitialized locals, set/sink and production emitted backends remain gated. */
IrProgram *ir_lower(Arena *arena, DiagBag *diagnostics, const SourceMap *sources, Program *program);
IrVerification ir_verify(const IrProgram *program);
/* Ordered manifest v1: domain tag, then little-endian u32 file count and
 * length-prefixed path/text bytes for each source. No filesystem reads. */
Str ir_source_manifest_hash(Arena *arena, const IrProgram *program);
bool ir_span_valid(const IrProgram *program, Span span);
uint32_t ir_type_cells(const IrProgram *program, IrType type);

typedef enum { IR_RUN_SUCCESS, IR_RUN_FAILED, IR_RUN_TRAP, IR_RUN_BUDGET,
    IR_RUN_IO, IR_RUN_INVALID, IR_RUN_UNAVAILABLE, IR_RUN_CANCELLED, IR_RUN_TIMEOUT } IrRunStatus;
typedef enum { IR_TRAP_NONE, IR_TRAP_OVERFLOW, IR_TRAP_DIVISION_ZERO, IR_TRAP_BOUNDS } IrTrap;
typedef struct {
    uint64_t max_steps, max_bytes; /* defaults: 1M steps, 64 MiB cumulative frames */
    uint32_t max_call_depth, timeout_ms; /* default depth 128, hard maximum 128 */
    FILE *output, *events;
    bool (*cancelled)(void);
    uint64_t (*clock_ms)(void);
} IrRunOpts;
typedef struct {
    IrRunStatus status;
    IrTrap trap;
    Span source;
    uint64_t steps, allocated_bytes, assertions;
    uint32_t tests, failed_tests;
    bool trace_complete;
} IrRunResult;
/* Independent IR execution; no AST evaluator or runtime arithmetic calls. */
IrRunResult ir_test(const IrProgram *program, IrRunOpts opts);
#endif
