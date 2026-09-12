#include "internal.h"
#include <math.h>
#include <stdio.h>

static int64_t signed_bits(uint32_t bits) {
    return bits<=INT32_MAX ? (int64_t)bits : (int64_t)bits-INT64_C(4294967296);
}
Value *ref_binary(Ref *r,TokKind op,Value *a,Value *b,Type *type,Span span) {
    if (!a || !b || r->result.status!=REF_SUCCESS) return NULL;
    if (a->type->kind==TY_BOOL) {
        if (op==TK_EQ) return ref_bool(r,a->as.b==b->as.b,span);
        if (op==TK_NE) return ref_bool(r,a->as.b!=b->as.b,span);
    }
    bool fp=a->type->kind==TY_FLOAT;
    if (op==TK_EQ || op==TK_NE || op==TK_LT || op==TK_LE || op==TK_GT || op==TK_GE) {
        double x=fp ? (double)a->as.f : (double)a->as.i;
        double y=fp ? (double)b->as.f : (double)b->as.i;
        bool answer=op==TK_EQ ? x==y : op==TK_NE ? x!=y : op==TK_LT ? x<y :
            op==TK_LE ? x<=y : op==TK_GT ? x>y : x>=y;
        return ref_bool(r,answer,span);
    }
    if (fp) {
        volatile float x=a->as.f, y=b->as.f, z=0;
        switch (op) {
            case TK_PLUS: z=x+y; break;
            case TK_MINUS: z=x-y; break;
            case TK_STAR: z=x*y; break;
            case TK_SLASH: z=x/y; break;
            default: ref_fail(r,REF_UNAVAILABLE,span,"this floating operation"); return NULL;
        }
        return ref_f32(r,z,span);
    }
    int64_t x=a->as.i,y=b->as.i,z=0;
    switch (op) {
        case TK_PLUS: z=x+y; break;
        case TK_MINUS: z=x-y; break;
        case TK_STAR: z=x*y; break; /* i32 product fits int64 */
        case TK_SLASH: case TK_PERCENT:
            if (!y) { ref_source_trap(r,REF_SOURCE_TRAP_DIV_ZERO,span,"integer division by zero"); return NULL; }
            if (x==INT32_MIN && y==-1) {
                if (op==TK_PERCENT) return ref_i32(r,0,span);
                ref_source_trap(r,REF_SOURCE_TRAP_OVERFLOW,span,"i32 division overflow"); return NULL;
            }
            z=op==TK_SLASH ? x/y : x%y; break;
        case TK_AMP: z=signed_bits((uint32_t)x & (uint32_t)y); break;
        case TK_PIPE: z=signed_bits((uint32_t)x | (uint32_t)y); break;
        case TK_CARET: z=signed_bits((uint32_t)x ^ (uint32_t)y); break;
        case TK_SHL: case TK_SHR: {
            if (y<0 || y>=32) { ref_fail(r,REF_TRAP,span,"shift count outside i32 width"); return NULL; }
            uint32_t bits=(uint32_t)x;
            if (op==TK_SHL) bits <<= (unsigned)y;
            else {
                bits >>= (unsigned)y;
                if (x<0 && y) bits |= UINT32_MAX << (32-(unsigned)y);
            }
            z=signed_bits(bits); break;
        }
        default: ref_fail(r,REF_UNAVAILABLE,span,"this integer operation"); return NULL;
    }
    return ref_i32(r,z,span);
}
Value *ref_intrinsic(Ref *r,Frame *frame,Expr *e) {
    uint32_t n=e->call.args.len;
    Value **args=ref_alloc(r,n,sizeof(Value *),e->span); if (!args) return NULL;
    for (uint32_t i=0;i<n;i++) { args[i]=ref_eval(r,frame,e->call.args.data[i].value); if (!args[i]) return NULL; }
    Intrinsic id=(Intrinsic)e->intrinsic;
    if (id==INTR_PRINT || id==INTR_PRINTLN) {
        ref_event(r,"print",e->span,id==INTR_PRINTLN);
        for (uint32_t i=0;i<n;i++) {
            Value *v=args[i]; char buffer[80]; int count=0;
            if (v->type->kind==TY_FLOAT) ref_event_f32(r,e->call.args.data[i].value->span,v->as.f);
            if (v->type->kind==TY_STR) { ref_write(r,r->opts.output,v->as.s,e->span); continue; }
            if (v->type->kind==TY_BOOL) count=snprintf(buffer,sizeof buffer,"%s",v->as.b?"true":"false");
            else if (v->type->kind==TY_FLOAT) count=snprintf(buffer,sizeof buffer,"%g",(double)v->as.f);
            else if (v->type->kind==TY_INT) count=snprintf(buffer,sizeof buffer,"%lld",(long long)v->as.i);
            else { ref_fail(r,REF_UNAVAILABLE,e->span,"printing aggregate values"); return NULL; }
            if (count<0 || (size_t)count>=sizeof buffer) { ref_fail(r,REF_IO,e->span,"numeric output encoding failed"); return NULL; }
            ref_write(r,r->opts.output,str_new(buffer,(uint32_t)count),e->span);
        }
        if (id==INTR_PRINTLN) ref_write(r,r->opts.output,str_from("\n"),e->span);
        return ref_zero(r,e->type,true,e->span);
    }
    if (id==INTR_ASSERT) {
        r->result.assertions++; ref_event(r,"assert",e->span,args[0]->as.b);
        if (!args[0]->as.b) {
            /* All failures remain in the bounded event stream; retain one
             * source diagnostic instead of allocating one per loop iteration. */
            if (!r->test_failed && !r->result.failed_tests) diag_error(r->d,1002,e->span,"reference assertion failed");
            r->test_failed=true;
        }
        return ref_zero(r,e->type,true,e->span);
    }
    Value *a=args[0]; bool fp=a->type->kind==TY_FLOAT;
    if (id>=INTR_WRAPPING_ADD && id<=INTR_SATURATING_SUB) {
        int64_t x=a->as.i,y=args[1]->as.i;
        if (id==INTR_SATURATING_ADD || id==INTR_SATURATING_SUB) {
            int64_t z=id==INTR_SATURATING_ADD ? x+y : x-y;
            return ref_i32(r,z<INT32_MIN?INT32_MIN:z>INT32_MAX?INT32_MAX:z,e->span);
        }
        uint32_t xbits=(uint32_t)x,ybits=(uint32_t)y;
        uint32_t z=id==INTR_WRAPPING_ADD ? xbits+ybits : id==INTR_WRAPPING_SUB ? xbits-ybits : xbits*ybits;
        return ref_i32(r,signed_bits(z),e->span);
    }
    double x=fp?(double)a->as.f:(double)a->as.i;
    if (id==INTR_ABS) return fp ? ref_f32(r,fabsf(a->as.f),e->span) : ref_i32(r,x<0?-a->as.i:a->as.i,e->span);
    if (id==INTR_SQRT) return ref_f32(r,sqrtf(a->as.f),e->span);
    double y=fp?(double)args[1]->as.f:(double)args[1]->as.i;
    if (id==INTR_MIN || id==INTR_MAX) return ref_copy(r,(id==INTR_MIN?x<y:x>y)?a:args[1],e->span);
    if (id==INTR_CLAMP) {
        double z=fp?(double)args[2]->as.f:(double)args[2]->as.i;
        return ref_copy(r,x<y?args[1]:x>z?args[2]:a,e->span);
    }
    ref_fail(r,REF_UNAVAILABLE,e->span,"this intrinsic"); return NULL;
}
