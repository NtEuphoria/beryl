#include "ir.h"
#include "../common/hash.h"
#include <stdlib.h>
#include <string.h>

enum { NORMAL=1u, RETURNED=2u, BROKEN=4u, CONTINUED=8u, YIELDED=16u };
/* Bit sets retain every possible logical state at a structured join. */
enum { NOT_DECLARED=1u, UNINITIALIZED=2u, INITIALIZED=4u, MOVED=8u };
typedef struct { uint8_t *breaks, *continues; bool has_break, has_continue; } LoopStates;
typedef struct {
    const IrProgram *p; IrVerification result;
    uint8_t *regions, *instructions, *values, *arguments, *captures;
    uint32_t *order;
} Verify;
static bool bad(Verify *v,Span at,const char *why) {
    if (v->result.ok) v->result=(IrVerification){.ok=false,.source=at,.reason=why};
    return false;
}
static bool within(uint32_t first,uint32_t count,uint32_t total) { return first<=total && count<=total-first; }
static bool exclusive_initializers(const IrProgram *p,uint32_t first,uint32_t second) {
    uint32_t ar=p->instructions.data[first].region;
    while (p->regions.data[ar].parent_instruction!=IR_NONE) {
        uint32_t ap=p->regions.data[ar].parent_instruction;
        if (p->instructions.data[ap].op==IR_IF) {
            uint32_t br=p->instructions.data[second].region;
            while (p->regions.data[br].parent_instruction!=IR_NONE) {
                uint32_t bp=p->regions.data[br].parent_instruction;
                if (bp==ap) return ar!=br; /* distinct immediate children of this IF */
                br=p->instructions.data[bp].region;
            }
        }
        ar=p->instructions.data[ap].region;
    }
    return false;
}
static bool shape(Verify *v,uint32_t r,uint32_t fn,uint32_t parent,IrRegionKind kind,uint32_t depth) {
    const IrProgram *p=v->p;
    if (depth>=IR_MAX_DEPTH || r>=p->regions.len) return bad(v,SPAN_NONE,"region index or nesting quota");
    const IrRegion *region=&p->regions.data[r];
    if (v->regions[r] || region->function!=fn || region->parent_instruction!=parent || region->kind!=kind)
        return bad(v,region->source,"region ownership, kind, sharing or cycle");
    v->regions[r]=1;
    uint32_t previous=IR_NONE, ordinal=0;
    for (uint32_t id=region->first;id!=IR_NONE;) {
        if (id>=p->instructions.len) return bad(v,region->source,"instruction index");
        const IrInstruction *i=&p->instructions.data[id];
        if (v->instructions[id] || i->region!=r || (uint32_t)i->op>(uint32_t)IR_MOVE) return bad(v,i->source.origin,"instruction ownership, opcode or cycle");
        if (!ir_span_valid(p,i->source.origin) || (i->source.has_expansion && !ir_span_valid(p,i->source.expansion)))
            return bad(v,i->source.origin,"instruction source span outside its captured source");
        v->instructions[id]=1; v->order[id]=ordinal++;
        if (i->result!=IR_NONE) {
            if (i->result>=p->values.len) return bad(v,i->source.origin,"result value index");
            const IrValue *value=&p->values.data[i->result];
            if (v->values[i->result] || value->function!=fn || value->definition!=id || (!ir_type_cells(p,value->type)))
                return bad(v,i->source.origin,"value ownership, duplicate definition or type");
            v->values[i->result]=1;
        }
        uint32_t children=i->op==IR_IF?2:i->op==IR_LOOP?3:0;
        for (uint32_t c=0;c<3;c++) {
            if (c>=children) {
                if (i->child[c]!=IR_NONE) return bad(v,i->source.origin,"unexpected child region");
            } else {
                IrRegionKind expected=i->op==IR_IF || c==1?IR_REGION_BRANCH:c==0?IR_REGION_CONDITION:IR_REGION_STEP;
                if (!shape(v,i->child[c],fn,id,expected,depth+1)) return false;
            }
        }
        if (i->op==IR_CALL || i->op==IR_PRINT || i->op==IR_ASSERT || i->op==IR_INTRINSIC || i->op==IR_RECORD || i->op==IR_ARRAY) {
            if (i->args_count>IR_MAX_CALL_ARGUMENTS || !within(i->args_start,i->args_count,p->arguments.len))
                return bad(v,i->source.origin,"argument range");
            for (uint32_t a=0;a<i->args_count;a++) {
                uint32_t index=i->args_start+a;
                if (v->arguments[index]) return bad(v,i->source.origin,"shared argument range");
                if (!ir_span_valid(p,p->arguments.data[index].source)) return bad(v,i->source.origin,"argument source span");
                v->arguments[index]=1;
            }
        } else if (i->args_count) return bad(v,i->source.origin,"arguments on a non-call instruction");
        previous=id; id=i->next;
    }
    if (region->last!=previous) return bad(v,region->source,"incorrect region tail");
    if (!ir_span_valid(p,region->source)) return bad(v,region->source,"region source span");
    return true;
}
static bool operand(Verify *v,uint32_t use,uint32_t value,IrType *type) {
    const IrProgram *p=v->p; const IrInstruction *i=&p->instructions.data[use];
    uint32_t fn=p->regions.data[i->region].function;
    if (value>=p->values.len || p->values.data[value].function!=fn) return bad(v,i->source.origin,"operand index or cross-function value");
    const IrValue *x=&p->values.data[value]; uint32_t definition=x->definition, at=use;
    uint32_t def_region=p->instructions.data[definition].region;
    for (uint32_t depth=0;p->instructions.data[at].region!=def_region;depth++) {
        if (depth>=IR_MAX_DEPTH) return bad(v,i->source.origin,"operand dominance depth");
        at=p->regions.data[p->instructions.data[at].region].parent_instruction;
        if (at==IR_NONE) return bad(v,i->source.origin,"value does not dominate this structured region");
    }
    if (v->order[definition]>=v->order[at]) return bad(v,i->source.origin,"value used before its definition");
    *type=x->type; return true;
}
/* Dynamic indices conservatively cover every admitted element. This is a
 * static overlap bound, not a guess about the eventual index value. */
static uint32_t place_range(const IrProgram *p,uint32_t place,uint32_t *lo,uint32_t *hi) {
    *lo=0; *hi=0;
    if (place>=p->places.len) return IR_NONE;
    uint32_t cells=ir_type_cells(p,p->places.data[place].type);
    for (uint32_t depth=0;place<p->places.len && depth<IR_MAX_DEPTH;depth++) {
        const IrPlace *x=&p->places.data[place];
        if (x->parent==IR_NONE) { *hi+=cells; return place; }
        if (x->parent>=place) return IR_NONE;
        if (x->definition!=IR_NONE) {
            IrType t=p->places.data[x->parent].type;
            if (t<IR_FIRST_AGGREGATE || t-IR_FIRST_AGGREGATE>=p->aggregates.len) return IR_NONE;
            const IrAggregate *array=&p->aggregates.data[t-IR_FIRST_AGGREGATE];
            if (array->kind!=IR_TYPE_ARRAY) return IR_NONE;
            if (array->length) *hi+=(array->length-1)*ir_type_cells(p,array->element);
        } else {
            if (x->field>=p->fields.len) return IR_NONE;
            *lo+=p->fields.data[x->field].offset; *hi+=p->fields.data[x->field].offset;
        }
        place=x->parent;
    }
    return IR_NONE;
}
static bool crosses_capture(const IrProgram *p,uint32_t instruction,uint32_t watched);
static bool place_access(Verify *v,uint32_t use,uint32_t place,uint8_t *init,bool writing) {
    const IrProgram *p=v->p; const IrInstruction *i=&p->instructions.data[use];
    if (place>=p->places.len || p->places.data[place].function!=p->regions.data[i->region].function)
        return bad(v,i->source.origin,"place index or ownership");
    uint32_t lo,hi,root=place_range(p,place,&lo,&hi);
    if (root==IR_NONE || init[root]!=INITIALIZED) return bad(v,i->source.origin,"place access before definite initialization");
    if (writing && !p->places.data[place].mutable) return bad(v,i->source.origin,"write or inout capture to immutable place");
    for (uint32_t at=place;p->places.data[at].parent!=IR_NONE;at=p->places.data[at].parent) {
        uint32_t def=p->places.data[at].definition;
        if (def!=IR_NONE && (def>=p->instructions.len || p->instructions.data[def].region!=i->region || v->order[def]>=v->order[use]))
            return bad(v,i->source.origin,"dynamic place used before definition or across a region boundary");
        if (def!=IR_NONE) for (uint32_t cursor=p->instructions.data[def].next;cursor!=use;cursor=p->instructions.data[cursor].next)
            if (cursor==IR_NONE || crosses_capture(p,cursor,at)) return bad(v,i->source.origin,"write or control effect crosses dynamic place interval");
    }
    return true;
}
static bool overlap(const IrProgram *p,uint32_t a,uint32_t b) {
    uint32_t al,ah,bl,bh,ar=place_range(p,a,&al,&ah),br=place_range(p,b,&bl,&bh);
    if (ar==IR_NONE || br==IR_NONE) return true;
    return ar==br && al<bh && bl<ah;
}
static bool crosses_capture(const IrProgram *p,uint32_t instruction,uint32_t watched) {
    if (instruction>=p->instructions.len) return true;
    const IrInstruction *i=&p->instructions.data[instruction];
    if (i->op==IR_INIT || i->op==IR_STORE || i->op==IR_DECLARE || i->op==IR_MOVE) return overlap(p,i->place,watched);
    if (i->op==IR_CALL) {
        if (!within(i->args_start,i->args_count,p->arguments.len)) return true;
        for (uint32_t a=0;a<i->args_count;a++) {
            const IrArgument *arg=&p->arguments.data[i->args_start+a];
            if ((uint32_t)arg->mode>(uint32_t)IR_SINK) return true;
            if (arg->mode==IR_INOUT || arg->mode==IR_SET) {
                if (!arg->by_place || arg->capture>=p->instructions.len || p->instructions.data[arg->capture].op!=IR_CAPTURE) return true;
                if (overlap(p,p->instructions.data[arg->capture].place,watched)) return true;
            }
        }
        return false; /* no globals or escaping references in this admitted IR */
    }
    return i->op==IR_IF || i->op==IR_LOOP || (i->effects&IR_EXIT);
}
/* SET and a whole-root assignment select storage without reading its old
 * logical value. Physical storage is untouched until the later STORE/CALL. */
static bool write_place(Verify *v,uint32_t use,uint32_t place,uint8_t *init) {
    const IrProgram *p=v->p; const IrInstruction *i=&p->instructions.data[use];
    if (place>=p->places.len || p->places.data[place].function!=p->regions.data[i->region].function)
        return bad(v,i->source.origin,"destination index or ownership");
    const IrPlace *q=&p->places.data[place];
    if (q->parent!=IR_NONE) return place_access(v,use,place,init,true);
    if (init[place]&NOT_DECLARED) return bad(v,i->source.origin,"destination before declaration");
    if (q->parameter && q->mode==IR_LET) return bad(v,i->source.origin,"write through let parameter");
    if (!q->mutable && (init[place]&INITIALIZED)) return bad(v,i->source.origin,"replacement of an initialized immutable root");
    return true;
}
static bool call_argument(Verify *v,uint32_t use,const IrArgument *arg,const IrPlace *parameter,uint8_t *init) {
    const IrProgram *p=v->p; const IrInstruction *call=&p->instructions.data[use]; IrType type;
    if (arg->mode!=parameter->mode) return bad(v,arg->source,"call argument mode");
    if (!arg->by_place) {
        if (arg->mode!=IR_LET && arg->mode!=IR_SINK) return bad(v,arg->source,"mutable argument is not a captured place");
        if (arg->mode==IR_SINK && arg->capture!=IR_NONE) {
            if (arg->capture>=p->instructions.len) return bad(v,arg->source,"move capture index");
            const IrInstruction *move=&p->instructions.data[arg->capture];
            if (move->op!=IR_MOVE || move->result!=arg->value || move->region!=call->region ||
                v->order[arg->capture]>=v->order[use] || v->captures[arg->capture]++)
                return bad(v,arg->source,"move capture ownership, reuse or order");
        } else if (arg->capture!=IR_NONE) return bad(v,arg->source,"unexpected value capture");
        return operand(v,use,arg->value,&type) && (type==parameter->type || bad(v,arg->source,"call argument type"));
    }
    if (arg->capture>=p->instructions.len) return bad(v,arg->source,"capture index");
    const IrInstruction *capture=&p->instructions.data[arg->capture];
    if (capture->op!=IR_CAPTURE || capture->region!=call->region || v->order[arg->capture]>=v->order[use] || v->captures[arg->capture]++)
        return bad(v,arg->source,"capture ownership, reuse or order");
    if (arg->mode==IR_SINK || capture->immediate!=(int32_t)arg->mode || capture->flag!=(arg->mode!=IR_LET))
        return bad(v,arg->source,"capture access mode");
    if (arg->mode==IR_SET) { if (!write_place(v,use,capture->place,init)) return false; }
    else if (!place_access(v,use,capture->place,init,arg->mode==IR_INOUT)) return false;
    if (p->places.data[capture->place].type!=parameter->type || (arg->mode==IR_LET && parameter->type<IR_FIRST_AGGREGATE))
        return bad(v,arg->source,"captured argument type");
    /* Interposed calls can write only through their explicit inout captures:
     * globals, escaped references and mutable let parameters are unavailable.
     * Reject overlap and conservatively reject branching intervals. */
    for (uint32_t at=capture->next;at!=use;at=p->instructions.data[at].next) {
        if (at==IR_NONE || crosses_capture(p,at,capture->place))
            return bad(v,arg->source,"write or control effect crosses captured argument interval");
    }
    return true;
}
static bool destination(Verify *v,uint32_t use) {
    const IrProgram *p=v->p; const IrInstruction *store=&p->instructions.data[use];
    if (p->places.data[store->place].parent==IR_NONE)
        return store->b==IR_NONE || bad(v,store->source.origin,"root store has an unexpected destination capture");
    if (store->b>=p->instructions.len) return bad(v,store->source.origin,"missing projected destination capture");
    const IrInstruction *capture=&p->instructions.data[store->b];
    if (capture->op!=IR_DESTINATION || capture->place!=store->place || capture->region!=store->region ||
        v->order[store->b]>=v->order[use] || v->captures[store->b]++) return bad(v,store->source.origin,"destination capture ownership or order");
    for (uint32_t at=capture->next;at!=use;at=p->instructions.data[at].next) {
        if (at==IR_NONE || crosses_capture(p,at,capture->place))
            return bad(v,capture->source.origin,"write or control effect crosses projected destination");
    }
    return true;
}
static bool output(Verify *v,const IrInstruction *i,IrType type) {
    if (type==IR_VOID) return i->result==IR_NONE || bad(v,i->source.origin,"unexpected result value");
    return (i->result<v->p->values.len && v->p->values.data[i->result].type==type) || bad(v,i->source.origin,"result type");
}
static uint8_t *copy_initialization(Verify *v,uint8_t *init,Span at) {
    size_t n=v->p->places.len?v->p->places.len:1;
    uint8_t *copy=malloc(n);
    if (!copy) { bad(v,at,"verifier allocation unavailable"); return NULL; }
    memcpy(copy,init,n); return copy;
}
static void merge_states(const IrProgram *p,uint8_t *to,const uint8_t *from,bool *present) {
    if (!*present) memcpy(to,from,p->places.len);
    else for (uint32_t n=0;n<p->places.len;n++) to[n]|=from[n];
    *present=true;
}
static void set_exit(Verify *v,const IrFunction *fn,const uint8_t *init,Span at) {
    for (uint32_t n=0;n<fn->parameters;n++) {
        uint32_t place=fn->places_start+n;
        if (v->p->places.data[place].mode==IR_SET && init[place]!=INITIALIZED)
            bad(v,at,"set parameter is not initialized on this return");
    }
}
static uint32_t semantics(Verify *v,uint32_t r,uint8_t *init,uint32_t loops,bool control,uint32_t *effects,LoopStates *loop) {
    const IrProgram *p=v->p; const IrRegion *region=&p->regions.data[r];
    const IrFunction *fn=&p->functions.data[region->function];
    uint32_t flow=NORMAL; *effects=0;
    for (uint32_t id=region->first;id!=IR_NONE && v->result.ok;id=p->instructions.data[id].next) {
        const IrInstruction *i=&p->instructions.data[id]; IrType a=IR_VOID,b=IR_VOID;
        uint32_t required=0, next=NORMAL;
        if (!(flow&NORMAL)) { bad(v,i->source.origin,"instructions after an unconditional region exit"); break; }
        switch (i->op) {
            case IR_CONST:
                if (i->result==IR_NONE || p->values.data[i->result].type>=IR_FIRST_AGGREGATE || (p->values.data[i->result].type==IR_BOOL && i->immediate!=0 && i->immediate!=1))
                    bad(v,i->source.origin,"constant type or bool representation");
                else if (p->values.data[i->result].type==IR_F32 && (i->float_bits&UINT32_C(0x7f800000))==UINT32_C(0x7f800000))
                    bad(v,i->source.origin,"nonfinite f32 constant");
                break;
            case IR_DECLARE: {
                if (i->place>=p->places.len) { bad(v,i->source.origin,"declaration place index"); break; }
                const IrPlace *q=&p->places.data[i->place];
                if (q->function!=region->function || q->parameter || q->synthetic || q->parent!=IR_NONE)
                    bad(v,i->source.origin,"declaration must reset one source local root");
                output(v,i,IR_VOID); required=IR_WRITE; init[i->place]=UNINITIALIZED; break;
            }
            case IR_LOAD: case IR_MOVE: case IR_INIT: case IR_STORE: {
                if (i->place>=p->places.len || p->places.data[i->place].function!=region->function) { bad(v,i->source.origin,"place index or ownership"); break; }
                const IrPlace *place=&p->places.data[i->place];
                if (i->op==IR_LOAD || i->op==IR_MOVE) {
                    place_access(v,id,i->place,init,false);
                    output(v,i,place->type); required=IR_READ;
                    if (i->op==IR_MOVE) {
                        if (place->parent!=IR_NONE || (place->parameter && place->mode!=IR_SINK && place->mode!=IR_SET))
                            bad(v,i->source.origin,"partial move or move from borrowed parameter");
                        init[i->place]=MOVED; required|=IR_WRITE;
                    }
                } else {
                    if (operand(v,id,i->a,&a) && a!=place->type) bad(v,i->source.origin,"stored value type");
                    output(v,i,IR_VOID); required=IR_WRITE;
                    if (i->op==IR_INIT) {
                        uint8_t expected=place->synthetic?NOT_DECLARED:UNINITIALIZED;
                        if (place->parameter || place->parent!=IR_NONE || init[i->place]!=expected)
                            bad(v,i->source.origin,"place reinitialization");
                    }
                    if (i->op==IR_STORE) { write_place(v,id,i->place,init); if (v->result.ok) destination(v,id); }
                    init[i->place]=INITIALIZED;
                }
                break;
            }
            case IR_UNARY:
                if (!operand(v,id,i->a,&a)) break;
                if (i->numeric==IR_NOT) { if (a!=IR_BOOL) bad(v,i->source.origin,"logical-not operand type"); output(v,i,IR_BOOL); }
                else if (i->numeric==IR_NEG || i->numeric==IR_BIT_NOT) {
                    if (a!=IR_I32 && !(a==IR_F32 && i->numeric==IR_NEG)) bad(v,i->source.origin,"numeric unary operand type");
                    output(v,i,a); required=i->numeric==IR_NEG?IR_FAILURE:0;
                } else bad(v,i->source.origin,"unary operation");
                break;
            case IR_BINARY:
                if (!operand(v,id,i->a,&a) || !operand(v,id,i->b,&b)) break;
                if (a>=IR_FIRST_AGGREGATE) bad(v,i->source.origin,"aggregate numeric comparison");
                if (a!=b) bad(v,i->source.origin,"binary operand types differ");
                if (i->numeric>=IR_ADD && i->numeric<=IR_BIT_XOR) {
                    if (a!=IR_I32 && !(a==IR_F32 && i->numeric<=IR_DIV)) bad(v,i->source.origin,"numeric binary operand type");
                    output(v,i,a); required=i->numeric<=IR_REM?IR_FAILURE:0;
                } else if (i->numeric>=IR_EQ && i->numeric<=IR_GE) {
                    if (i->numeric>IR_NE && a!=IR_I32 && a!=IR_F32) bad(v,i->source.origin,"ordered comparison operand type");
                    output(v,i,IR_BOOL);
                } else if (i->numeric==IR_SHL || i->numeric==IR_SHR) {
                    if (a!=IR_I32) bad(v,i->source.origin,"shift operand type");
                    output(v,i,IR_I32); required=IR_FAILURE;
                } else bad(v,i->source.origin,"binary operation");
                break;
            case IR_CAST:
                if (!operand(v,id,i->a,&a)) break;
                if (a>=IR_FIRST_AGGREGATE) bad(v,i->source.origin,"aggregate cast operand");
                if (i->result==IR_NONE || (p->values.data[i->result].type!=IR_I32 && p->values.data[i->result].type!=IR_F32))
                    bad(v,i->source.origin,"cast destination type");
                required=IR_FAILURE; break;
            case IR_INTRINSIC: {
                for (uint32_t n=0;n<i->args_count;n++) if (p->arguments.data[i->args_start+n].by_place || p->arguments.data[i->args_start+n].mode!=IR_LET) bad(v,i->source.origin,"intrinsic place argument");
                if ((uint32_t)i->intrinsic>(uint32_t)IR_SAT_SUB) { bad(v,i->source.origin,"intrinsic kind"); break; }
                uint32_t count=i->intrinsic==IR_ABS?1:i->intrinsic==IR_CLAMP?3:2;
                if (i->args_count!=count) { bad(v,i->source.origin,"numeric intrinsic arity"); break; }
                if (!operand(v,id,p->arguments.data[i->args_start].value,&a)) break;
                if ((a!=IR_I32 && a!=IR_F32) || (i->intrinsic>=IR_WRAP_ADD && a!=IR_I32)) bad(v,i->source.origin,"numeric intrinsic type");
                for (uint32_t n=1;n<count && v->result.ok;n++)
                    if (operand(v,id,p->arguments.data[i->args_start+n].value,&b) && b!=a) bad(v,i->source.origin,"intrinsic operand types differ");
                output(v,i,a); required=IR_FAILURE; break;
            }
            case IR_CALL: case IR_PRINT: case IR_ASSERT:
                if (i->op==IR_CALL) {
                    if (i->function>=p->functions.len || p->functions.data[i->function].test) { bad(v,i->source.origin,"call target"); break; }
                    const IrFunction *callee=&p->functions.data[i->function];
                    if (i->args_count!=callee->parameters) { bad(v,i->source.origin,"call arity"); break; }
                    for (uint32_t n=0;n<i->args_count && v->result.ok;n++) {
                        const IrArgument *arg=&p->arguments.data[i->args_start+n];
                        call_argument(v,id,arg,&p->places.data[callee->places_start+n],init);
                        if (!arg->by_place || !v->result.ok) continue;
                        uint32_t captured=p->instructions.data[arg->capture].place;
                        for (uint32_t previous=0;previous<n;previous++) {
                            const IrArgument *prior=&p->arguments.data[i->args_start+previous];
                            if (!prior->by_place || (prior->mode==IR_LET && arg->mode==IR_LET)) continue;
                            if (overlap(p,captured,p->instructions.data[prior->capture].place)) bad(v,arg->source,"overlapping captured mutable arguments");
                        }
                    }
                    /* SET commits logical initialization only after every capture is checked. */
                    for (uint32_t n=0;n<i->args_count && v->result.ok;n++) {
                        const IrArgument *arg=&p->arguments.data[i->args_start+n];
                        if (arg->mode==IR_SET) {
                            uint32_t place=p->instructions.data[arg->capture].place;
                            if (p->places.data[place].parent==IR_NONE) init[place]=INITIALIZED;
                        }
                    }
                    output(v,i,callee->result); required=IR_ALL_EFFECTS;
                } else {
                    output(v,i,IR_VOID); required=IR_OBSERVE|IR_FAILURE;
                    if (i->op==IR_ASSERT && i->args_count!=1) { bad(v,i->source.origin,"assert arity"); break; }
                    if (i->op==IR_PRINT && i->args_count>1) { bad(v,i->source.origin,"print arity"); break; }
                    for (uint32_t n=0;n<i->args_count && v->result.ok;n++) {
                        const IrArgument *arg=&p->arguments.data[i->args_start+n];
                        if (arg->by_place || arg->mode!=IR_LET) bad(v,arg->source,"observation place argument");
                        if (operand(v,id,arg->value,&a) && ((i->op==IR_ASSERT && a!=IR_BOOL) || a>=IR_FIRST_AGGREGATE))
                            bad(v,i->source.origin,"observation operand type");
                    }
                }
                break;
            case IR_DESTINATION:
                place_access(v,id,i->place,init,true); output(v,i,IR_VOID); required=IR_READ; break;
            case IR_CAPTURE:
                if (i->immediate<IR_LET || i->immediate>IR_SET || i->flag!=(i->immediate!=IR_LET))
                    bad(v,i->source.origin,"capture mode encoding");
                if (i->immediate==IR_SET) write_place(v,id,i->place,init);
                else place_access(v,id,i->place,init,i->flag);
                output(v,i,IR_VOID); required=i->immediate==IR_SET?0:IR_READ; break;
            case IR_RECORD: {
                if (i->result==IR_NONE || p->values.data[i->result].type<IR_FIRST_AGGREGATE) { bad(v,i->source.origin,"record result type"); break; }
                const IrAggregate *record=&p->aggregates.data[p->values.data[i->result].type-IR_FIRST_AGGREGATE];
                if (record->kind!=IR_TYPE_RECORD || i->args_count!=record->fields_count) { bad(v,i->source.origin,"record construction arity"); break; }
                uint8_t seen[IR_MAX_CELLS]={0};
                for (uint32_t n=0;n<i->args_count && v->result.ok;n++) {
                    const IrArgument *arg=&p->arguments.data[i->args_start+n];
                    if (arg->by_place || arg->mode!=IR_LET || arg->field<record->fields_start || arg->field-record->fields_start>=record->fields_count || seen[arg->field-record->fields_start]++) {
                        bad(v,arg->source,"duplicate, missing or incompatible record field"); break;
                    }
                    if (operand(v,id,arg->value,&a) && a!=p->fields.data[arg->field].type) bad(v,arg->source,"record field value type");
                }
                break;
            }
            case IR_FIELD: {
                if (!operand(v,id,i->a,&a)) break;
                if (a<IR_FIRST_AGGREGATE) { bad(v,i->source.origin,"field base type"); break; }
                const IrAggregate *record=&p->aggregates.data[a-IR_FIRST_AGGREGATE];
                if (record->kind!=IR_TYPE_RECORD || i->place<record->fields_start || i->place-record->fields_start>=record->fields_count) { bad(v,i->source.origin,"field declaration identity"); break; }
                output(v,i,p->fields.data[i->place].type); break;
            }
            case IR_ARRAY: {
                if (i->result==IR_NONE || p->values.data[i->result].type<IR_FIRST_AGGREGATE) { bad(v,i->source.origin,"array result type"); break; }
                const IrAggregate *array=&p->aggregates.data[p->values.data[i->result].type-IR_FIRST_AGGREGATE];
                if (array->kind!=IR_TYPE_ARRAY || i->args_count!=array->length) { bad(v,i->source.origin,"array construction arity"); break; }
                for (uint32_t n=0;n<i->args_count && v->result.ok;n++) {
                    const IrArgument *arg=&p->arguments.data[i->args_start+n];
                    if (arg->by_place || arg->mode!=IR_LET || arg->field!=n) { bad(v,arg->source,"array element order or mode"); break; }
                    if (operand(v,id,arg->value,&a) && a!=array->element) bad(v,arg->source,"array element value type");
                }
                break;
            }
            case IR_INDEX_VALUE: {
                if (!operand(v,id,i->a,&a) || !operand(v,id,i->b,&b)) break;
                if (a<IR_FIRST_AGGREGATE || p->aggregates.data[a-IR_FIRST_AGGREGATE].kind!=IR_TYPE_ARRAY || b!=IR_I32) { bad(v,i->source.origin,"value index operand types"); break; }
                output(v,i,p->aggregates.data[a-IR_FIRST_AGGREGATE].element); required=IR_FAILURE; break;
            }
            case IR_INDEX_BASE:
                if (!place_access(v,id,i->place,init,false)) break;
                a=p->places.data[i->place].type;
                if (a<IR_FIRST_AGGREGATE || p->aggregates.data[a-IR_FIRST_AGGREGATE].kind!=IR_TYPE_ARRAY) bad(v,i->source.origin,"index capture base type");
                output(v,i,IR_VOID); required=IR_READ; break;
            case IR_INDEX_PLACE: {
                if (i->place>=p->places.len || p->places.data[i->place].definition!=id) { bad(v,i->source.origin,"index place definition"); break; }
                const IrPlace *place=&p->places.data[i->place];
                if (place->parent==IR_NONE || !place_access(v,id,place->parent,init,false)) { bad(v,i->source.origin,"index place parent"); break; }
                if (operand(v,id,i->a,&a) && a!=IR_I32) bad(v,i->source.origin,"place index operand type");
                if (i->b>=p->instructions.len) { bad(v,i->source.origin,"missing index base capture"); break; }
                const IrInstruction *capture=&p->instructions.data[i->b];
                if (capture->op!=IR_INDEX_BASE || capture->place!=place->parent || capture->region!=i->region || v->order[i->b]>=v->order[id] || v->captures[i->b]++) { bad(v,i->source.origin,"index base capture ownership or order"); break; }
                for (uint32_t at=capture->next;at!=id;at=p->instructions.data[at].next) {
                    if (at==IR_NONE || crosses_capture(p,at,capture->place)) { bad(v,capture->source.origin,"write or control effect crosses index base capture"); break; }
                }
                output(v,i,IR_VOID); required=IR_READ|IR_FAILURE; break;
            }
            case IR_IF: {
                if (!operand(v,id,i->a,&a)) break;
                if (a!=IR_BOOL) bad(v,i->source.origin,"if condition type"); output(v,i,IR_VOID);
                uint8_t *yes=copy_initialization(v,init,i->source.origin), *no=copy_initialization(v,init,i->source.origin);
                uint32_t ye=0,ne=0,yf=0,nf=0;
                if (yes && no && v->result.ok) {
                    yf=semantics(v,i->child[0],yes,loops,control,&ye,loop);
                    nf=semantics(v,i->child[1],no,loops,control,&ne,loop);
                    for (uint32_t pidx=0;pidx<p->places.len;pidx++) {
                        if ((yf&NORMAL) && (nf&NORMAL)) init[pidx]=yes[pidx] | no[pidx];
                        else if (yf&NORMAL) init[pidx]=yes[pidx];
                        else if (nf&NORMAL) init[pidx]=no[pidx];
                    }
                }
                free(yes); free(no); required=ye|ne; next=yf|nf; break;
            }
            case IR_LOOP: {
                output(v,i,IR_VOID); uint32_t ce=0,be=0,se=0;
                uint8_t *head=copy_initialization(v,init,i->source.origin);
                uint32_t cf=semantics(v,i->child[0],init,0,false,&ce,NULL);
                if (cf!=YIELDED) bad(v,i->source.origin,"loop condition must yield exactly one bool");
                uint8_t *body=copy_initialization(v,init,i->source.origin), *step=copy_initialization(v,init,i->source.origin);
                LoopStates exits={.breaks=copy_initialization(v,init,i->source.origin),.continues=copy_initialization(v,init,i->source.origin)};
                uint32_t bf=0,sf=0;
                if (head && body && step && exits.breaks && exits.continues && v->result.ok) {
                    bf=semantics(v,i->child[1],body,loops+1,control,&be,&exits);
                    bool step_present=false;
                    if (bf&NORMAL) merge_states(p,step,body,&step_present);
                    if (exits.has_continue) merge_states(p,step,exits.continues,&step_present);
                    sf=semantics(v,i->child[2],step,0,false,&se,NULL);
                    if (sf!=NORMAL || (bf&YIELDED)) bad(v,i->source.origin,"invalid loop body or step exit");
                    if (step_present) for (uint32_t n=0;n<p->places.len;n++) {
                        /* Newly declared body locals restart their own lifetime.
                         * Outer roots must retain the same head state on every
                         * back edge; more general state-changing loops are gated. */
                        if (head[n]!=NOT_DECLARED && step[n]!=head[n])
                            bad(v,i->source.origin,"loop back edge changes an outer logical state");
                    }
                    if (exits.has_break) for (uint32_t n=0;n<p->places.len;n++) init[n]|=exits.breaks[n];
                }
                free(head); free(body); free(step); free(exits.breaks); free(exits.continues);
                required=ce|be|se; next=NORMAL|(bf&RETURNED); break;
            }
            case IR_RETURN:
                if (!control) bad(v,i->source.origin,"return inside a condition or step");
                if (fn->result==IR_VOID) { if (i->a!=IR_NONE) bad(v,i->source.origin,"void return value"); }
                else if (operand(v,id,i->a,&a) && a!=fn->result) bad(v,i->source.origin,"return type");
                set_exit(v,fn,init,i->source.origin);
                output(v,i,IR_VOID); required=IR_EXIT; next=RETURNED; break;
            case IR_BREAK: case IR_CONTINUE:
                if (!loops || !control || !loop) bad(v,i->source.origin,"loop exit outside a loop body");
                else if (i->op==IR_BREAK) merge_states(p,loop->breaks,init,&loop->has_break);
                else merge_states(p,loop->continues,init,&loop->has_continue);
                output(v,i,IR_VOID); required=IR_EXIT; next=i->op==IR_BREAK?BROKEN:CONTINUED; break;
            case IR_YIELD:
                if (region->kind!=IR_REGION_CONDITION) bad(v,i->source.origin,"yield outside a loop condition region");
                if (operand(v,id,i->a,&a) && a!=IR_BOOL) bad(v,i->source.origin,"condition yield type");
                output(v,i,IR_VOID); required=IR_EXIT; next=YIELDED; break;
        }
        if ((i->effects&~IR_ALL_EFFECTS) || (i->effects&required)!=required) bad(v,i->source.origin,"missing required or unknown effects");
        *effects|=i->effects; flow=(flow&~NORMAL)|next;
    }
    return flow;
}
IrVerification ir_verify(const IrProgram *p) {
    Verify v={.p=p,.result={.ok=true,.source=SPAN_NONE,.reason="valid"}};
    if (!p || p->schema_version!=IR_SCHEMA_VERSION || p->aggregates.len>IR_MAX_TYPES || p->fields.len>IR_MAX_FIELDS || p->functions.len>IR_MAX_FUNCTIONS || p->places.len>IR_MAX_PLACES ||
        p->values.len>IR_MAX_VALUES || p->instructions.len>IR_MAX_INSTRUCTIONS || p->regions.len>IR_MAX_REGIONS || p->arguments.len>IR_MAX_ARGUMENTS)
        return (IrVerification){.ok=false,.source=SPAN_NONE,.reason="schema version or table quota"};
    if ((p->aggregates.len && !p->aggregates.data) || (p->fields.len && !p->fields.data) || (p->functions.len && !p->functions.data) || (p->places.len && !p->places.data) || (p->values.len && !p->values.data) ||
        (p->instructions.len && !p->instructions.data) || (p->regions.len && !p->regions.data) || (p->arguments.len && !p->arguments.data))
        return (IrVerification){.ok=false,.source=SPAN_NONE,.reason="missing table storage"};
    if (!p->sources.len || p->sources.len>IR_MAX_SOURCE_FILES || !p->sources.data || p->source_manifest_sha256.len!=64 || !p->source_manifest_sha256.ptr)
        return (IrVerification){.ok=false,.source=SPAN_NONE,.reason="missing source manifest"};
    uint64_t source_bytes=0; Arena *hashes=arena_new(0);
    for (uint32_t f=0;f<p->sources.len && v.result.ok;f++) {
        const IrSourceFile *file=&p->sources.data[f];
        if (!file->path.len || file->path.len>32768 || !file->path.ptr || (file->text.len && !file->text.ptr) ||
            file->text.len>IR_MAX_SOURCE_BYTES-source_bytes || file->sha256.len!=64 || !file->sha256.ptr) {
            bad(&v,SPAN_NONE,"source manifest storage or byte quota"); break;
        }
        source_bytes+=file->text.len;
        if (!str_eq(hash256_str(hashes,file->text),file->sha256)) bad(&v,SPAN_NONE,"source content hash mismatch");
    }
    if (v.result.ok && !str_eq(ir_source_manifest_hash(hashes,p),p->source_manifest_sha256)) bad(&v,SPAN_NONE,"ordered source manifest hash mismatch");
    arena_free(hashes); if (!v.result.ok) return v.result;
    uint32_t field_end=0;
    for (uint32_t t=0;t<p->aggregates.len && v.result.ok;t++) {
        const IrAggregate *record=&p->aggregates.data[t];
        if ((uint32_t)record->kind>(uint32_t)IR_TYPE_ARRAY || !ir_span_valid(p,record->declaration) || record->fields_start!=field_end || !within(record->fields_start,record->fields_count,p->fields.len)) { bad(&v,record->declaration,"aggregate declaration, kind or field range"); break; }
        if (record->kind==IR_TYPE_ARRAY) {
            if (record->identity.len || record->fields_count || record->element==IR_VOID || record->element>=IR_FIRST_AGGREGATE+t || record->length>IR_MAX_CELLS) { bad(&v,record->declaration,"array identity, length or element type"); break; }
            uint32_t element_cells=ir_type_cells(p,record->element);
            if (!element_cells || (record->length && element_cells>IR_MAX_CELLS/record->length) || record->cells!=(record->length?record->length*element_cells:1)) { bad(&v,record->declaration,"array cell count"); break; }
            for (uint32_t earlier=0;earlier<t;earlier++) {
                const IrAggregate *old=&p->aggregates.data[earlier];
                if (old->kind==IR_TYPE_ARRAY && old->element==record->element && old->length==record->length) bad(&v,record->declaration,"duplicate structural array type");
            }
            continue;
        }
        if (!record->identity.len || !record->identity.ptr || !record->fields_count || record->fields_count>IR_MAX_CELLS || record->element!=IR_VOID || record->length) { bad(&v,record->declaration,"record declaration or field range"); break; }
        for (uint32_t earlier=0;earlier<t;earlier++) if (p->aggregates.data[earlier].kind==IR_TYPE_RECORD && str_eq(record->identity,p->aggregates.data[earlier].identity)) bad(&v,record->declaration,"duplicate record identity");
        uint32_t cells=0;
        for (uint32_t f=0;f<record->fields_count && v.result.ok;f++) {
            const IrField *field=&p->fields.data[field_end+f];
            if (!field->identity.len || !field->identity.ptr || !ir_span_valid(p,field->declaration) || field->type==IR_VOID || field->type>=IR_FIRST_AGGREGATE+t ||
                field->offset!=cells || ir_type_cells(p,field->type)>IR_MAX_CELLS-cells) { bad(&v,field->declaration,"field identity, topological type or offset"); break; }
            for (uint32_t old=0;old<f;old++) if (str_eq(field->identity,p->fields.data[field_end+old].identity)) bad(&v,field->declaration,"duplicate field identity");
            cells+=ir_type_cells(p,field->type);
        }
        if (cells!=record->cells || !cells || cells>IR_MAX_CELLS) bad(&v,record->declaration,"record cell count");
        field_end+=record->fields_count;
    }
    if (field_end!=p->fields.len) bad(&v,SPAN_NONE,"unowned field entries");
    if (!v.result.ok) return v.result;
    v.regions=calloc(p->regions.len?p->regions.len:1,1); v.instructions=calloc(p->instructions.len?p->instructions.len:1,1);
    v.values=calloc(p->values.len?p->values.len:1,1); v.arguments=calloc(p->arguments.len?p->arguments.len:1,1);
    v.captures=calloc(p->instructions.len?p->instructions.len:1,1);
    v.order=calloc(p->instructions.len?p->instructions.len:1,sizeof(uint32_t));
    uint8_t *init=calloc(p->places.len?p->places.len:1,1);
    if (!v.regions || !v.instructions || !v.values || !v.arguments || !v.order || !v.captures || !init) bad(&v,SPAN_NONE,"verifier allocation unavailable");
    uint32_t place_end=0,value_end=0;
    for (uint32_t f=0;f<p->functions.len && v.result.ok;f++) {
        const IrFunction *fn=&p->functions.data[f];
        if ((fn->result!=IR_VOID && !ir_type_cells(p,fn->result)) || fn->places_start!=place_end || fn->values_start!=value_end ||
            !within(fn->places_start,fn->places_count,p->places.len) || !within(fn->values_start,fn->values_count,p->values.len) ||
            fn->parameters>fn->places_count || fn->parameters>IR_MAX_CALL_ARGUMENTS || (fn->test && (fn->parameters || fn->result!=IR_VOID))) {
            bad(&v,fn->declaration,"function signature or table ranges"); break;
        }
        if (!ir_span_valid(p,fn->declaration)) { bad(&v,fn->declaration,"function declaration source span"); break; }
        place_end+=fn->places_count; value_end+=fn->values_count;
        for (uint32_t x=fn->places_start;x<place_end;x++) {
            const IrPlace *place=&p->places.data[x];
            if (place->function!=f || (!ir_type_cells(p,place->type)) || place->parameter!=(x-fn->places_start<fn->parameters) ||
                (place->parameter && ((uint32_t)place->mode>(uint32_t)IR_SINK || place->mutable!=(place->mode!=IR_LET)))) { bad(&v,place->declaration,"place type, parameter or ownership"); break; }
            if (place->parent!=IR_NONE) {
                if (place->parent<fn->places_start || place->parent>=x || place->parameter || place->mode!=IR_LET || place->mutable!=p->places.data[place->parent].mutable) { bad(&v,place->declaration,"projection parent, mode or mutability"); break; }
                IrType parent=p->places.data[place->parent].type;
                if (parent<IR_FIRST_AGGREGATE) { bad(&v,place->declaration,"projection parent is not a record"); break; }
                const IrAggregate *record=&p->aggregates.data[parent-IR_FIRST_AGGREGATE];
                if (record->kind==IR_TYPE_ARRAY) {
                    if (place->field!=IR_NONE || place->type!=record->element || place->definition>=p->instructions.len || p->instructions.data[place->definition].op!=IR_INDEX_PLACE || p->instructions.data[place->definition].place!=x) { bad(&v,place->declaration,"array projection identity or type"); break; }
                } else if (place->definition!=IR_NONE || place->field<record->fields_start || place->field-record->fields_start>=record->fields_count || p->fields.data[place->field].type!=place->type) { bad(&v,place->declaration,"projection field identity or type"); break; }
            } else if (place->field!=IR_NONE || place->definition!=IR_NONE) { bad(&v,place->declaration,"root has a projection identity"); break; }
            if (!ir_span_valid(p,place->declaration)) { bad(&v,place->declaration,"place declaration source span"); break; }
        }
        for (uint32_t x=fn->values_start;x<value_end;x++) if (p->values.data[x].function!=f) bad(&v,fn->declaration,"value function range");
        if (v.result.ok) shape(&v,fn->body,f,IR_NONE,IR_REGION_BODY,0);
    }
    if (place_end!=p->places.len || value_end!=p->values.len) bad(&v,SPAN_NONE,"unowned place or value table entries");
    if (v.result.ok) {
        for (uint32_t i=0;i<p->regions.len;i++) if (!v.regions[i]) bad(&v,p->regions.data[i].source,"unowned region");
        for (uint32_t i=0;i<p->instructions.len;i++) if (!v.instructions[i]) bad(&v,p->instructions.data[i].source.origin,"unowned instruction");
        for (uint32_t i=0;i<p->values.len;i++) if (!v.values[i]) bad(&v,SPAN_NONE,"undefined value");
        for (uint32_t i=0;i<p->arguments.len;i++) if (!v.arguments[i]) bad(&v,SPAN_NONE,"unowned arguments");
    }
    if (v.result.ok) {
        /* A scalar declaration may execute repeatedly through a loop. A
         * distinct INIT instruction must not bypass immutable STORE checks.
         * The only admitted multi-site case is the two mutually exclusive
         * branch definitions of a short-circuit temporary. */
        uint32_t first[IR_MAX_PLACES]; uint8_t count[IR_MAX_PLACES]={0}, declarations[IR_MAX_PLACES]={0};
        for (uint32_t i=0;i<p->instructions.len && v.result.ok;i++) {
            const IrInstruction *inst=&p->instructions.data[i];
            if (inst->op==IR_DECLARE) {
                if (inst->place>=p->places.len || declarations[inst->place]++) bad(&v,inst->source.origin,"duplicate or invalid local lifetime declaration");
            }
            if (inst->op!=IR_INIT) continue;
            if (inst->place>=p->places.len) { bad(&v,inst->source.origin,"initialization place index"); break; }
            if (!count[inst->place]) first[inst->place]=i;
            else if (count[inst->place]>=2 || !exclusive_initializers(p,first[inst->place],i))
                bad(&v,inst->source.origin,"multiple initialization sites are not mutually exclusive");
            count[inst->place]++;
        }
    }
    for (uint32_t f=0;f<p->functions.len && v.result.ok;f++) {
        memset(init,NOT_DECLARED,p->places.len); const IrFunction *fn=&p->functions.data[f];
        for (uint32_t x=0;x<fn->parameters;x++) init[fn->places_start+x]=p->places.data[fn->places_start+x].mode==IR_SET?UNINITIALIZED:INITIALIZED;
        uint32_t effects=0, flow=semantics(&v,fn->body,init,0,true,&effects,NULL);
        if (flow!=RETURNED) bad(&v,fn->declaration,"function has an implicit or invalid exit");
    }
    if (v.result.ok) for (uint32_t i=0;i<p->instructions.len;i++) if ((p->instructions.data[i].op==IR_CAPTURE || p->instructions.data[i].op==IR_DESTINATION || p->instructions.data[i].op==IR_INDEX_BASE || p->instructions.data[i].op==IR_MOVE) && !v.captures[i]) bad(&v,p->instructions.data[i].source.origin,"unconsumed argument capture");
    free(v.captures); free(v.regions); free(v.instructions); free(v.values); free(v.arguments); free(v.order); free(init);
    return v.result;
}
