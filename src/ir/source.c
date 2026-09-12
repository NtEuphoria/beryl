#include "ir.h"
#include "../common/hash.h"
static void length(Hash256 *h,uint32_t n) {
    unsigned char bytes[4]={(unsigned char)n,(unsigned char)(n>>8),(unsigned char)(n>>16),(unsigned char)(n>>24)};
    hash256_update(h,bytes,sizeof bytes);
}
Str ir_source_manifest_hash(Arena *a,const IrProgram *p) {
    Hash256 h; hash256_init(&h); const char domain[]="beryl-ir-source-manifest-v1";
    hash256_update(&h,domain,sizeof domain-1); length(&h,p->sources.len);
    for (uint32_t f=0;f<p->sources.len;f++) {
        const IrSourceFile *s=&p->sources.data[f];
        length(&h,s->path.len); hash256_update(&h,s->path.ptr,s->path.len);
        length(&h,s->text.len); hash256_update(&h,s->text.ptr,s->text.len);
    }
    return hash256_finish(a,&h);
}
bool ir_span_valid(const IrProgram *p,Span span) {
    if (!p || span.file>=p->sources.len) return false;
    uint32_t size=p->sources.data[span.file].text.len;
    return span.offset<=size && span.len<=size-span.offset;
}

uint32_t ir_type_cells(const IrProgram *p,IrType type) {
    if (type==IR_VOID) return 0;
    if (type<IR_FIRST_AGGREGATE) return 1;
    uint32_t id=type-IR_FIRST_AGGREGATE;
    return id<p->aggregates.len?p->aggregates.data[id].cells:0;
}
