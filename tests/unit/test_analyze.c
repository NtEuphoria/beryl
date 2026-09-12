#include "test.h"
#include "../../src/driver/analyze.h"
#include "../../src/common/hash.h"
#include "../../src/common/json.h"
#include <string.h>

static AnalyzeSnapshot snapshot(Arena *a,AnalyzeSource *source,const char *text){
    *source=(AnalyzeSource){.path=STR_LIT("src/example.be"),.text=str_from(text),.document_version=7};
    source->sha256=hash256_str(a,source->text);
    return(AnalyzeSnapshot){.request_id=STR_LIT("unit.1"),.snapshot_version=19,.target=ANALYZE_NATIVE,.forbid_unsafe=true,.sources=source,.source_count=1};
}
typedef struct {uint32_t calls;Str bytes;bool fail;} ReadFixture;
static bool read_fixture(void *ctx,Arena *a,Str name,Str *bytes){(void)a;ReadFixture *f=ctx;f->calls++;CHECK_EQ_S(name,"0001.be");*bytes=f->bytes;return!f->fail;}
static Str request(Arena *a,Str bytes,const char *extra,const char *content){
    SB b;sb_init(&b,a);sb_cstr(&b,"{\"schema_version\":1,\"request_id\":\"test.1\",\"snapshot_version\":4,\"target\":\"native\",\"forbid_unsafe\":true,\"sources\":[{\"path\":\"src/main.be\",\"sha256\":");json_string(&b,hash256_str(a,bytes));
    sb_cstr(&b,",\"document_version\":8,\"content_file\":");json_string(&b,str_from(content));sb_cstr(&b,"}]");sb_cstr(&b,extra);sb_char(&b,'}');return sb_finish(&b);
}
void run_analyze_tests(void){
    CASE("analysis: exact snapshot reuses target semantics without execution");
    Arena *a=arena_new(0);AnalyzeSource source;AnalyzeSnapshot s=snapshot(a,&source,"module example\nfn main() { let x = 1 + 2 }\n");
    AnalyzeResult r=analyze_snapshot(a,&s,"test");CHECK_EQ_I(r.exit_code,0);CHECK_CONTAINS(r.json,"\"status\":\"success\"");
    CHECK_CONTAINS(r.json,"\"document_version\":7");CHECK_CONTAINS(r.json,"\"execution\":\"not_run\"");CHECK_CONTAINS(r.json,"\"snapshot_fingerprint\":\"");
    s.target=ANALYZE_ENFUSION;r=analyze_snapshot(a,&s,"test");CHECK_EQ_I(r.exit_code,0);
    s.target=ANALYZE_REFERENCE;r=analyze_snapshot(a,&s,"test");CHECK_EQ_I(r.exit_code,0);
    arena_free(a);

    CASE("analysis: original byte locations survive Unicode and CRLF overlays");
    a=arena_new(0);s=snapshot(a,&source,"module example\r\n// \xce\xbb overlay\r\nfn main() { let x = missing }\r\n");
    r=analyze_snapshot(a,&s,"test");CHECK_EQ_I(r.exit_code,1);CHECK_CONTAINS(r.json,"src/example.be");CHECK_CONTAINS(r.json,"\"column_unit\":\"byte\"");
    CHECK_CONTAINS(r.json,"BE0301");CHECK_CONTAINS(r.json,"\"snapshot_fingerprint\":\"");arena_free(a);

    CASE("analysis: wrong hashes, invalid UTF-8 and invalid metadata never admit");
    a=arena_new(0);s=snapshot(a,&source,"module example\nfn main() {}\n");source.sha256=hash256_str(a,STR_LIT("different"));
    r=analyze_snapshot(a,&s,"test");CHECK_EQ_I(r.exit_code,2);CHECK_EQ_S(str_from(r.status),"stale_input");
    s=snapshot(a,&source,"module example\n\xff");r=analyze_snapshot(a,&s,"test");CHECK_EQ_I(r.exit_code,1);CHECK_EQ_S(str_from(r.stage),"source_encoding");
    s=snapshot(a,&source,"module example\n");s.request_id=STR_LIT("bad id");CHECK_EQ_I(analyze_snapshot(a,&s,"test").exit_code,1);
    s=snapshot(a,&source,"module example\n");source.path=STR_LIT("../outside.be");CHECK_EQ_I(analyze_snapshot(a,&s,"test").exit_code,1);
    s=snapshot(a,&source,"module example\n");s.expected_compiler_sha256=hash256_str(a,STR_LIT("different compiler"));CHECK_EQ_I(analyze_snapshot(a,&s,"test").exit_code,2);
    s=snapshot(a,&source,"module example\n");AnalyzeSource dup[2]={source,source};dup[1].path=STR_LIT("SRC/EXAMPLE.be");s.sources=dup;s.source_count=2;CHECK_EQ_I(analyze_snapshot(a,&s,"test").exit_code,1);
    arena_free(a);

    CASE("analysis: whole request schema is validated before content reads");
    a=arena_new(0);ReadFixture f={.bytes=STR_LIT("module example\nfn main() {}\n")};
    Str good=request(a,f.bytes,"","0001.be");r=analyze_request(a,good,read_fixture,&f,"test");CHECK_EQ_I(r.exit_code,0);CHECK_EQ_I(f.calls,1);
    f.calls=0;r=analyze_request(a,request(a,f.bytes,",\"shell\":\"no\"","0001.be"),read_fixture,&f,"test");CHECK_EQ_I(r.exit_code,1);CHECK_EQ_I(f.calls,0);
    r=analyze_request(a,request(a,f.bytes,",\"request_id\":\"duplicate\"","0001.be"),read_fixture,&f,"test");CHECK_EQ_I(r.exit_code,1);CHECK_EQ_I(f.calls,0);
    const char *bad_names[]={"../0001.be","C:/0001.be","folder/0001.be","a\\0001.be","a:0001.be","CON","nul.be","LPT1.be",".hidden","trailing."};
    for(size_t i=0;i<sizeof(bad_names)/sizeof(*bad_names);i++){r=analyze_request(a,request(a,f.bytes,"",bad_names[i]),read_fixture,&f,"test");CHECK_EQ_I(r.exit_code,1);CHECK_EQ_I(f.calls,0);}
    f.fail=true;r=analyze_request(a,good,read_fixture,&f,"test");CHECK_EQ_I(r.exit_code,1);CHECK_EQ_S(str_from(r.stage),"source_read");CHECK_EQ_I(f.calls,1);
    f.calls=0;
    r=analyze_request(a,str_new(NULL,1),read_fixture,&f,"test");CHECK_EQ_I(r.exit_code,1);CHECK_EQ_I(f.calls,0);
    /* Length must be rejected before dereferencing or hashing this tiny buffer. */
    r=analyze_request(a,str_new("x",1048577),read_fixture,&f,"test");CHECK_EQ_I(r.exit_code,1);CHECK_EQ_I(f.calls,0);
    arena_free(a);

    CASE("analysis: semantic ownership, taint and target admission are real passes");
    a=arena_new(0);s=snapshot(a,&source,"module example\n@untrusted\nfn input(i:i32) -> i32 { let a = [1,2]\n return a[i] }\n");
    r=analyze_snapshot(a,&s,"test");CHECK_EQ_I(r.exit_code,1);CHECK_CONTAINS(r.json,"BE0601");
    s=snapshot(a,&source,"module example\nfn main() { var xs: List<i32>\n xs.push(1) }\n");s.target=ANALYZE_REFERENCE;
    r=analyze_snapshot(a,&s,"test");CHECK_EQ_I(r.exit_code,3);CHECK_EQ_S(str_from(r.status),"unavailable");CHECK_CONTAINS(r.json,"\"admission\":{\"target\":\"reference\",\"status\":\"unavailable\"");
    arena_free(a);
}
