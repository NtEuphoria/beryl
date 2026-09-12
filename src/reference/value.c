#include "internal.h"
#include "../common/json.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stddef.h>

struct Allocation { Allocation *next; max_align_t alignment; };

const char *reference_status_name(RefStatus status) {
    switch (status) {
        case REF_SUCCESS: return "success";
        case REF_FAILED: return "failure";
        case REF_UNAVAILABLE: return "unavailable";
        case REF_TRAP: return "trap";
        case REF_BUDGET: return "budget_exhausted";
        case REF_IO: return "io_failure";
        case REF_TIMEOUT: return "timeout";
        case REF_CANCELLED: return "cancelled";
    }
    return "failure";
}
const char *reference_trap_kind_name(RefTrapKind kind) {
    switch (kind) {
        case REF_SOURCE_TRAP_OVERFLOW: return "overflow";
        case REF_SOURCE_TRAP_DIV_ZERO: return "division_by_zero";
        case REF_SOURCE_TRAP_BOUNDS: return "bounds";
        default: return "none";
    }
}
void ref_fail(Ref *r,RefStatus status,Span span,const char *reason) {
    if (r->result.status!=REF_SUCCESS) return;
    r->result.status=status;
    /* The driver verifies an explicit expected source trap separately. Other
     * failures (including limits and unsupported domains) remain diagnostics. */
    if (status==REF_TRAP && r->opts.expected_trap.enabled &&
        r->result.trap_kind!=REF_SOURCE_TRAP_NONE) return;
    diag_error(r->d,status==REF_UNAVAILABLE ? 1001 : status==REF_BUDGET ? 1003 :
        status==REF_IO ? 1004 : status==REF_TIMEOUT || status==REF_CANCELLED ? 1005 : 1002,span,"reference execution: %s",reason);
}
static bool ref_watch_snapshot(Ref *r,Span trap) {
    if (!r->opts.watch_root.enabled) return true;
    Value *root=r->watch_root;
    if (!root || !ref_readable(r,root,trap)) {
        if (r->result.status==REF_SUCCESS)
            ref_fail(r,REF_UNAVAILABLE,trap,"the watched root is not active and initialized at the source trap");
        return false;
    }
    uint64_t count=root->type->array_len; char buffer[200];
    uint32_t file=r->opts.watch_root.file, offset=r->opts.watch_root.offset;
    int n=snprintf(buffer,sizeof buffer,
        "{\"event\":\"root_begin\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"length\":%llu,\"element\":\"i32\"}\n",
        (unsigned long long)r->event_number++,file,offset,(unsigned long long)count);
    if (n<0 || (size_t)n>=sizeof buffer || !ref_write(r,r->opts.events,str_new(buffer,(uint32_t)n),trap)) return false;
    for (uint64_t i=0;i<count;i++) {
        n=snprintf(buffer,sizeof buffer,
            "{\"event\":\"root_i32\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"index\":%llu,\"value\":%lld}\n",
            (unsigned long long)r->event_number++,file,offset,(unsigned long long)i,(long long)root->as.members[i]->as.i);
        if (n<0 || (size_t)n>=sizeof buffer || !ref_write(r,r->opts.events,str_new(buffer,(uint32_t)n),trap)) return false;
    }
    n=snprintf(buffer,sizeof buffer,
        "{\"event\":\"root_end\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"length\":%llu}\n",
        (unsigned long long)r->event_number++,file,offset,(unsigned long long)count);
    return n>=0 && (size_t)n<sizeof buffer && ref_write(r,r->opts.events,str_new(buffer,(uint32_t)n),trap);
}
void ref_source_trap(Ref *r,RefTrapKind kind,Span span,const char *reason) {
    if (r->result.status!=REF_SUCCESS) return;
    r->result.trap_kind=kind; r->result.trap_span=span;
    if (r->opts.events) {
        if (!ref_watch_snapshot(r,span)) return;
        /* A terminal marker certifies the complete preceding observation
         * stream, including buffered stdout. Write/flush failure is never a
         * successfully observed source trap. */
        if (fflush(r->opts.output)!=0 || fflush(r->opts.events)!=0) {
            ref_fail(r,REF_IO,span,"cannot flush observations before source trap"); return;
        }
        char buffer[200];
        int n=snprintf(buffer,sizeof buffer,
            "{\"event\":\"source_trap\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"kind\":\"%s\",\"complete\":true}\n",
            (unsigned long long)r->event_number++,span.file,span.offset,reference_trap_kind_name(kind));
        if (n<0 || (size_t)n>=sizeof buffer) {
            ref_fail(r,REF_IO,span,"source-trap event encoding failed"); return;
        }
        if (!ref_write(r,r->opts.events,str_new(buffer,(uint32_t)n),span)) return;
        if (fflush(r->opts.events)!=0) {
            ref_fail(r,REF_IO,span,"source-trap event flush failed"); return;
        }
        r->result.trap_trace_complete=true;
    }
    ref_fail(r,REF_TRAP,span,reason);
}
bool ref_step(Ref *r,Span span) {
    if (r->result.status!=REF_SUCCESS) return false;
    if (r->opts.cancelled && r->opts.cancelled()) { ref_fail(r,REF_CANCELLED,span,"execution cancelled"); return false; }
    if (r->opts.clock_ms && r->opts.timeout_ms && r->opts.clock_ms()-r->started_ms>=r->opts.timeout_ms) {
        ref_fail(r,REF_TIMEOUT,span,"execution timed out"); return false;
    }
    if (r->result.steps>=r->opts.max_steps) { ref_fail(r,REF_BUDGET,span,"step budget exhausted"); return false; }
    r->result.steps++; return true;
}
void *ref_alloc(Ref *r,size_t count,size_t size,Span span) {
    if (r->result.status!=REF_SUCCESS) return NULL;
    if (size && count>(SIZE_MAX-sizeof(Allocation))/size) {
        ref_fail(r,REF_BUDGET,span,"allocation size exceeds the host range"); return NULL;
    }
    size_t bytes=count*size+sizeof(Allocation);
    if (r->result.bytes>r->opts.max_bytes || bytes>r->opts.max_bytes-r->result.bytes) {
        ref_fail(r,REF_BUDGET,span,"cumulative allocation budget exhausted"); return NULL;
    }
    Allocation *a=calloc(1,bytes);
    if (!a) { ref_fail(r,REF_BUDGET,span,"host allocation failed"); return NULL; }
    a->next=r->allocations; r->allocations=a; r->result.bytes+=bytes;
    return a+1;
}
static uint64_t members(Type *type) {
    if (type->kind==TY_ARRAY) return type->array_len;
    return type->kind==TY_STRUCT ? type->decl->strukt.fields.len : 0;
}
Value *ref_zero(Ref *r,Type *type,bool initialized,Span span) {
    Value *v=ref_alloc(r,1,sizeof(Value),span); if (!v) return NULL;
    v->type=type ? type : r->t_void; v->initialized=initialized;
    uint64_t n=members(v->type);
    if (n) {
        v->as.members=ref_alloc(r,(size_t)n,sizeof(Value *),span);
        if (!v->as.members) return NULL;
        for (uint64_t i=0;i<n;i++) {
            Type *elem=v->type->kind==TY_ARRAY ? v->type->elem : v->type->decl->strukt.fields.data[i].rtype;
            v->as.members[i]=ref_zero(r,elem,initialized,span);
            if (!v->as.members[i]) return NULL;
        }
    }
    return v;
}
bool ref_readable(Ref *r,Value *v,Span span) {
    if (!v || r->result.status!=REF_SUCCESS) return false;
    uint64_t n=members(v->type);
    if (v->type->kind==TY_ARRAY || v->type->kind==TY_STRUCT) {
        for (uint64_t i=0;i<n;i++) if (!ref_readable(r,v->as.members[i],span)) return false;
        return true;
    }
    if (!v->initialized) { ref_fail(r,REF_TRAP,span,"read of uninitialized or moved storage"); return false; }
    return true;
}
Value *ref_copy(Ref *r,Value *source,Span span) {
    if (!ref_readable(r,source,span)) return NULL;
    Value *v=ref_alloc(r,1,sizeof(Value),span); if (!v) return NULL;
    *v=*source;
    uint64_t n=members(v->type);
    if (n) {
        v->as.members=ref_alloc(r,(size_t)n,sizeof(Value *),span); if (!v->as.members) return NULL;
        for (uint64_t i=0;i<n;i++) {
            v->as.members[i]=ref_copy(r,source->as.members[i],span);
            if (!v->as.members[i]) return NULL;
        }
    }
    return v;
}
Value *ref_i32(Ref *r,int64_t i,Span span) {
    if (i<INT32_MIN || i>INT32_MAX) { ref_source_trap(r,REF_SOURCE_TRAP_OVERFLOW,span,"i32 arithmetic overflow"); return NULL; }
    Value *v=ref_zero(r,r->t_i32,true,span); if (v) v->as.i=i; return v;
}
Value *ref_f32(Ref *r,float f,Span span) {
    if (!isfinite(f)) { ref_fail(r,REF_TRAP,span,"nonfinite result outside the admitted numeric domain"); return NULL; }
    Value *v=ref_zero(r,r->t_f32,true,span); if (v) v->as.f=f; return v;
}
Value *ref_bool(Ref *r,bool b,Span span) {
    Value *v=ref_zero(r,r->t_bool,true,span); if (v) v->as.b=b; return v;
}
bool ref_write(Ref *r,FILE *file,Str value,Span span) {
    if (!file || r->result.status!=REF_SUCCESS) return false;
    if (r->output_bytes>64*1024*1024 || value.len>64*1024*1024-r->output_bytes) {
        ref_fail(r,REF_BUDGET,span,"output budget exhausted"); return false;
    }
    r->output_bytes+=value.len;
    if (fwrite(value.ptr,1,value.len,file)!=value.len) { ref_fail(r,REF_IO,span,"output write failed"); return false; }
    return true;
}
void ref_event(Ref *r,const char *kind,Span span,bool flag) {
    if (!r->opts.events || r->result.status!=REF_SUCCESS) return;
    char buffer[200];
    int n=snprintf(buffer,sizeof buffer,"{\"event\":\"%s\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"flag\":%s}\n",
        kind,(unsigned long long)r->event_number++,span.file,span.offset,flag?"true":"false");
    if (n<0 || (size_t)n>=sizeof buffer) { ref_fail(r,REF_IO,span,"event encoding failed"); return; }
    ref_write(r,r->opts.events,str_new(buffer,(uint32_t)n),span);
}
void ref_event_f32(Ref *r,Span span,float value) {
    if (!r->opts.events || r->result.status!=REF_SUCCESS) return;
    _Static_assert(sizeof(float)==sizeof(uint32_t),"reference requires binary32 float storage");
    uint32_t bits; memcpy(&bits,&value,sizeof bits);
    char buffer[200];
    int n=snprintf(buffer,sizeof buffer,"{\"event\":\"f32\",\"seq\":%llu,\"file\":%u,\"offset\":%u,\"bits\":%u}\n",
        (unsigned long long)r->event_number++,span.file,span.offset,bits);
    if (n<0 || (size_t)n>=sizeof buffer) { ref_fail(r,REF_IO,span,"event encoding failed"); return; }
    ref_write(r,r->opts.events,str_new(buffer,(uint32_t)n),span);
}

static bool watch_admit(DiagBag *d,Program *p,RefOpts opts) {
    if (!opts.watch_root.enabled) return true;
    Span at={opts.watch_root.file,opts.watch_root.offset,0};
    Item *test=NULL; uint32_t count=0;
    for (uint32_t m=0;m<p->modules.len;m++) for (uint32_t i=0;i<p->modules.data[m]->items.len;i++) {
        Item *it=p->modules.data[m]->items.data[i];
        if (it->kind==IT_TEST) { test=it; count++; }
    }
    if (!opts.expected_trap.enabled || count!=1 || !test->test.body || test->test.body->kind!=EX_BLOCK) {
        diag_error(d,1001,at,"root observation requires an expected source trap and exactly one test block"); return false;
    }
    for (uint32_t i=0;i<test->test.body->block.stmts.len;i++) {
        Stmt *s=test->test.body->block.stmts.data[i];
        if (s->kind!=ST_LET || !s->let.init || s->span.file!=at.file || s->span.offset!=at.offset) continue;
        Type *t=s->let.init->type;
        if (t && t->kind==TY_ARRAY && t->array_len>0 && t->array_len<=4096 &&
            t->elem && t->elem->kind==TY_INT && t->elem->bits==32 && t->elem->is_signed) return true;
        break;
    }
    diag_error(d,1001,at,"root observation supports a top-level initialized test-local [i32; N], with 1 <= N <= 4096");
    return false;
}
RefResult reference_test(DiagBag *d,Program *p,RefOpts opts) {
    Ref r={.d=d,.p=p,.opts=opts};
    if (!reference_admit(d,p)) return (RefResult){.status=REF_UNAVAILABLE};
    if (!watch_admit(d,p,opts)) return (RefResult){.status=REF_UNAVAILABLE};
    if (!r.opts.max_steps) r.opts.max_steps=1000000;
    if (!r.opts.max_bytes) r.opts.max_bytes=64*1024*1024;
    if (!r.opts.max_call_depth) r.opts.max_call_depth=128;
    if (!r.opts.output) r.opts.output=stdout;
    r.t_void=ty_prim(p->types,TY_VOID); r.t_bool=ty_prim(p->types,TY_BOOL);
    r.t_i32=ty_int(p->types,32,true); r.t_f32=ty_float(p->types,32);
    if (r.opts.clock_ms) r.started_ms=r.opts.clock_ms();
    for (uint32_t m=0;m<p->modules.len && r.result.status==REF_SUCCESS;m++) {
        Module *mod=p->modules.data[m];
        for (uint32_t i=0;i<mod->items.len && r.result.status==REF_SUCCESS;i++) {
            Item *it=mod->items.data[i]; if (it->kind!=IT_TEST || !it->test.body) continue;
            Frame frame={.item=it}; r.test_failed=false;
            frame.locals=ref_alloc(&r,it->nlocals,sizeof(Value *),it->span);
            if (!frame.locals) break;
            r.result.tests++; ref_event(&r,"test_begin",it->span,true);
            ref_eval(&r,&frame,it->test.body);
            if (r.test_failed) r.result.failed_tests++;
            ref_event(&r,"test_end",it->span,!r.test_failed);
        }
    }
    if (r.result.status==REF_SUCCESS && !r.result.tests) ref_fail(&r,REF_UNAVAILABLE,SPAN_NONE,"no test blocks selected");
    if (r.result.status==REF_SUCCESS) {
        char buffer[160]; int n;
        if (r.result.failed_tests) n=snprintf(buffer,sizeof buffer,"FAILED  %u of %u test%s\n",r.result.failed_tests,r.result.tests,r.result.tests==1?"":"s");
        else n=snprintf(buffer,sizeof buffer,"ok  %u test%s, %llu assertion%s\n",r.result.tests,r.result.tests==1?"":"s",
            (unsigned long long)r.result.assertions,r.result.assertions==1?"":"s");
        if (n>0 && (size_t)n<sizeof buffer) ref_write(&r,r.opts.output,str_new(buffer,(uint32_t)n),SPAN_NONE);
        if (r.result.failed_tests && r.result.status==REF_SUCCESS) r.result.status=REF_FAILED;
    }
    if (fflush(r.opts.output)!=0 || (r.opts.events && fflush(r.opts.events)!=0)) {
        if (r.result.status==REF_SUCCESS) ref_fail(&r,REF_IO,SPAN_NONE,"output flush failed");
    }
    while (r.allocations) { Allocation *a=r.allocations; r.allocations=a->next; free(a); }
    return r.result;
}
