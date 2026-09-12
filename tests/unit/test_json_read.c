#include "test.h"
#include "../../src/common/json_read.h"
#include <string.h>

static JsonValue *read_text(Arena *a,const char *text,JsonReadError *e){return json_read(a,str_from(text),json_read_limits(),e);}
static void reject_json(const char *text){Arena *a=arena_new(0);JsonReadError e={0};CHECK(!read_text(a,text,&e));CHECK(e.message);CHECK(e.offset<=strlen(text));arena_free(a);}
void run_json_read_tests(void){
    CASE("JSON reader: complete values, decoded text, source offsets and unsigned numbers");
    Arena *a=arena_new(0);JsonReadError e={0};
    JsonValue *v=read_text(a," {\"a\":[true,false,null,-2.5e+2],\"n\":9007199254740991,\"s\":\"\\u0041\\uD83D\\uDE80\\n\"} ",&e);
    CHECK(v&&v->kind==JR_OBJECT);CHECK(!e.message);CHECK_EQ_I(v?v->offset:0,1);
    JsonValue *list=json_member(v,"a");CHECK(list&&list->count==4);CHECK(list&&list->child->boolean);
    CHECK(list&&list->child->next->kind==JR_BOOL&&!list->child->next->boolean);
    CHECK_EQ_S(json_member(v,"s")->text,"A\xf0\x9f\x9a\x80\n");uint64_t n=0;
    CHECK(json_u64(json_member(v,"n"),UINT64_C(9007199254740991),&n));CHECK_EQ_I(n,UINT64_C(9007199254740991));
    CHECK(!json_u64(json_member(v,"n"),100,&n));CHECK(!json_u64(list->child->next->next->next,UINT64_MAX,&n));
    CHECK(!json_member(v,"missing"));CHECK(!json_member(list,"a"));
    JsonValue *zero=read_text(a,"0",&e);CHECK(json_u64(zero,0,&n));CHECK_EQ_I(n,0);
    CHECK(!json_u64(read_text(a,"1e0",&e),10,&n));CHECK(!json_u64(read_text(a,"1.0",&e),10,&n));
    CHECK(!json_u64(read_text(a,"18446744073709551616",&e),UINT64_MAX,&n));
    arena_free(a);

    CASE("JSON reader: grammar and decoded duplicate names fail closed");
    const char *invalid[]={""," ","{}x","[1,]","{\"a\":1,}","{\"a\" 1}","{a:1}","[01]","-","1.","1e", "+1","NaN","Infinity","tru","true false","[1 2]","{\"a\":1,\"a\":2}","{\"a\":1,\"\\u0061\":2}","{\"\\u0000\":1,\"\\u0000\":2}","\"x\n\"","\"\\x\"","\"\\u12\"","\"\\ud800\"","\"\\udc00\"","\"\\ud800\\u0041\"","\"\\ud800x\"","\"unterminated"};
    for(size_t i=0;i<sizeof(invalid)/sizeof(*invalid);i++)reject_json(invalid[i]);

    CASE("JSON reader: strict Unicode including invalid raw encodings");
    const char *bad_utf[]={"\"\xc0\xaf\"","\"\xed\xa0\x80\"","\"\xf4\x90\x80\x80\"","\"\x80\"","\"\xe2\x82\"","\xef\xbb\xbf{}"};
    for(size_t i=0;i<sizeof(bad_utf)/sizeof(*bad_utf);i++)reject_json(bad_utf[i]);
    a=arena_new(0);v=read_text(a,"\"\\u0000\\u007f\\u0080\\u0800\\uFFFF\\uDBFF\\uDFFF\"",&e);
    CHECK(v);CHECK(v&&v->text.len==14);CHECK(v&&v->text.ptr[0]==0);CHECK(v&&json_utf8(v->text,NULL));
    uint32_t bad=42;CHECK(!json_utf8(str_new("\xf4\x90\x80\x80",4),&bad));CHECK_EQ_I(bad,0);arena_free(a);

    CASE("JSON reader: all advertised limits fail with structured resource errors");
    JsonLimits limits=json_read_limits();a=arena_new(0);limits.bytes=1;
    CHECK(!json_read(a,STR_LIT("[]"),limits,&e)&&e.limit);limits=json_read_limits();limits.nodes=2;
    CHECK(!json_read(a,STR_LIT("[1,2]"),limits,&e)&&e.limit);limits=json_read_limits();limits.depth=2;
    CHECK(!json_read(a,STR_LIT("[[0]]"),limits,&e)&&e.limit);limits=json_read_limits();limits.string_bytes=2;
    CHECK(!json_read(a,STR_LIT("\"abc\""),limits,&e)&&e.limit);limits=json_read_limits();limits.work=2;
    CHECK(!json_read(a,STR_LIT("[1]"),limits,&e)&&e.limit);limits=json_read_limits();limits.depth=129;
    CHECK(!json_read(a,STR_LIT("0"),limits,&e));arena_free(a);

    CASE("JSON reader: deterministic bounded malformed-input corpus");
    uint32_t rng=0x812fab5u;
    for(uint32_t trial=0;trial<2000;trial++){
        char bytes[96];rng=rng*1664525u+1013904223u;uint32_t length=rng%sizeof(bytes);
        for(uint32_t i=0;i<length;i++){rng=rng*1664525u+1013904223u;bytes[i]=(char)(rng>>24);}
        a=arena_new(0);v=json_read(a,str_new(bytes,length),json_read_limits(),&e);
        CHECK((v!=NULL)==(e.message==NULL));CHECK(e.offset<=length);arena_free(a);
    }
    CASE("JSON reader: structured seed mutations enter nested parsing paths");
    const char seed[]="{\"name\":\"\\uD83D\\uDE80\",\"values\":[true,123,null,{\"x\":-1.5e2}]}";
    for(uint32_t trial=0;trial<1000;trial++){
        char bytes[sizeof(seed)];memcpy(bytes,seed,sizeof(seed));rng=rng*1664525u+1013904223u;
        uint32_t length=(uint32_t)strlen(seed),position=rng%length;
        if(trial%3==0)length=position;
        else {rng=rng*1664525u+1013904223u;bytes[position]="{}[],:\\\"012tfn \x80"[rng%16];}
        a=arena_new(0);v=json_read(a,str_new(bytes,length),json_read_limits(),&e);
        CHECK((v!=NULL)==(e.message==NULL));CHECK(e.offset<=length);arena_free(a);
    }
}
