#ifndef BERYL_REFERENCE_INTERNAL_H
#define BERYL_REFERENCE_INTERNAL_H
#include "reference.h"
#include "../sema/intrinsic.h"
#include <stdint.h>

typedef struct Value Value;
struct Value {
    Type *type;
    bool initialized;
    union { int64_t i; float f; bool b; Str s; Value **members; } as;
};
typedef enum { FLOW_NORMAL, FLOW_RETURN, FLOW_BREAK, FLOW_CONTINUE } Flow;
typedef struct { Item *item; Value **locals; Flow flow; Value *returned; } Frame;
typedef struct Allocation Allocation;
typedef struct {
    DiagBag *d; Program *p; RefOpts opts; RefResult result;
    Type *t_void, *t_i32, *t_f32, *t_bool;
    Allocation *allocations;
    uint32_t call_depth, eval_depth, constant_depth;
    uint64_t output_bytes, event_number;
    uint64_t started_ms;
    bool test_failed;
    Value *watch_root;
} Ref;

void ref_fail(Ref *r,RefStatus status,Span span,const char *reason);
void ref_source_trap(Ref *r,RefTrapKind kind,Span span,const char *reason);
bool ref_step(Ref *r,Span span);
void *ref_alloc(Ref *r,size_t count,size_t size,Span span);
Value *ref_zero(Ref *r,Type *type,bool initialized,Span span);
Value *ref_copy(Ref *r,Value *value,Span span);
bool ref_readable(Ref *r,Value *value,Span span);
Value *ref_eval(Ref *r,Frame *frame,Expr *expr);
Value *ref_place(Ref *r,Frame *frame,Expr *expr);
void ref_stmt(Ref *r,Frame *frame,Stmt *stmt);
Value *ref_call(Ref *r,Frame *caller,Expr *call);
Value *ref_binary(Ref *r,TokKind op,Value *a,Value *b,Type *type,Span span);
Value *ref_intrinsic(Ref *r,Frame *frame,Expr *expr);
Value *ref_i32(Ref *r,int64_t value,Span span);
Value *ref_f32(Ref *r,float value,Span span);
Value *ref_bool(Ref *r,bool value,Span span);
bool ref_write(Ref *r,FILE *file,Str value,Span span);
void ref_event(Ref *r,const char *kind,Span span,bool flag);
void ref_event_f32(Ref *r,Span span,float value);
#endif
