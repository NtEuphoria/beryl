#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include "analyze.h"
#include "identity.h"
#include "../common/fs.h"
#include "../common/hash.h"
#include "../common/json.h"
#include "../common/json_read.h"
#include "process.h"
#include "../lex/lexer.h"
#include "../parse/parser.h"
#include "../sema/check.h"
#include "../sema/ownership.h"
#include "../sema/taint.h"
#include "../back/c_backend.h"
#include "../back/enforce_backend.h"
#include "../reference/reference.h"
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

static void js(SB *b,const char *s){json_string(b,str_from(s));}
static void optional(SB *b,Str s){if(s.len)json_string(b,s);else sb_cstr(b,"null");}
static const char *target_name(AnalyzeTarget t){return t==ANALYZE_NATIVE?"native":t==ANALYZE_ENFUSION?"enfusion":t==ANALYZE_REFERENCE?"reference":"unknown";}
static bool ascii_letter(char c){return(c>='a'&&c<='z')||(c>='A'&&c<='Z');}
static bool ascii_digit(char c){return c>='0'&&c<='9';}
static char fold(char c){return(c>='A'&&c<='Z')?(char)(c+('a'-'A')):c;}
static bool folded_equal(Str a,Str b){if(a.len!=b.len)return false;for(uint32_t i=0;i<a.len;i++)if(fold(a.ptr[i])!=fold(b.ptr[i]))return false;return true;}
static bool token(Str s,uint32_t max){if(!s.ptr||!s.len||s.len>max)return false;for(uint32_t i=0;i<s.len;i++){char c=s.ptr[i];if(!ascii_letter(c)&&!ascii_digit(c)&&c!='_'&&c!='-'&&c!='.')return false;}return true;}
static bool hash_valid(Str s){if(!s.ptr||s.len!=64)return false;for(uint32_t i=0;i<s.len;i++)if(!ascii_digit(s.ptr[i])&&(s.ptr[i]<'a'||s.ptr[i]>'f'))return false;return true;}
static bool logical_path(Str s){
    if(!s.ptr||!s.len||s.len>1024||!json_utf8(s,NULL))return false;
    uint32_t start=0;
    for(uint32_t i=0;i<=s.len;i++) {
        if(i<s.len) {unsigned char c=(unsigned char)s.ptr[i];if(c<32||c==127||c=='\\'||c==':'||c=='"'||c=='<'||c=='>'||c=='|'||c=='?'||c=='*')return false;if(c!='/')continue;}
        Str part=str_slice(s,start,i-start);
        if(!part.len||str_eq_c(part,".")||str_eq_c(part,"..")||part.ptr[part.len-1]==' '||part.ptr[part.len-1]=='.')return false;
        start=i+1;
    }
    return s.len>3&&!memcmp(s.ptr+s.len-3,".be",3);
}
static bool content_name(Str s){
    if(!token(s,128)||(!ascii_letter(s.ptr[0])&&!ascii_digit(s.ptr[0]))||s.ptr[s.len-1]=='.')return false;
    uint32_t len=0;while(len<s.len&&s.ptr[len]!='.')len++;
    Str base=str_slice(s,0,len);
    if(folded_equal(base,STR_LIT("con"))||folded_equal(base,STR_LIT("prn"))||folded_equal(base,STR_LIT("aux"))||folded_equal(base,STR_LIT("nul")))return false;
    if(len==4&&s.ptr[3]>='1'&&s.ptr[3]<='9'&&(folded_equal(str_slice(s,0,3),STR_LIT("com"))||folded_equal(str_slice(s,0,3),STR_LIT("lpt"))))return false;
    return true;
}
static Str descriptors(Arena *a,const AnalyzeSnapshot *s){
    SB b;sb_init(&b,a);sb_char(&b,'[');
    for(uint32_t i=0;i<s->source_count;i++){const AnalyzeSource *f=&s->sources[i];if(i)sb_char(&b,',');
        sb_cstr(&b,"{\"path\":");json_string(&b,f->path);sb_cstr(&b,",\"sha256\":");json_string(&b,f->sha256);
        sb_fmt(&b,",\"document_version\":%llu,\"file_id\":%u}",(unsigned long long)f->document_version,i);}
    sb_char(&b,']');return sb_finish(&b);
}
static Str snapshot_identity(Arena *a,const AnalyzeSnapshot *s){
    SB b;sb_init(&b,a);sb_cstr(&b,"{\"identity_schema\":\"beryl.analysis.snapshot.v1\",\"request_id\":");json_string(&b,s->request_id);
    sb_fmt(&b,",\"snapshot_version\":%llu,\"target\":",(unsigned long long)s->snapshot_version);js(&b,target_name(s->target));
    sb_fmt(&b,",\"forbid_unsafe\":%s,\"sources\":",s->forbid_unsafe?"true":"false");sb_str(&b,descriptors(a,s));sb_char(&b,'}');return hash256_str(a,sb_finish(&b));
}
static AnalyzeResult result(Arena *a,const AnalyzeSnapshot *s,SourceMap *sm,DiagBag *d,
                             const char *version,Str compiler,const char *status,const char *stage,
                             int code,bool identified,bool admitted){
    SB b;sb_init(&b,a);sb_cstr(&b,"{\"schema_version\":1,\"operation\":\"analyze\",\"stage\":");js(&b,stage);
    sb_cstr(&b,",\"status\":");js(&b,status);uint32_t identity_start=b.len;
    sb_cstr(&b,",\"request_id\":");optional(&b,s?s->request_id:STR_EMPTY);
    sb_cstr(&b,",\"snapshot_version\":");if(s)sb_fmt(&b,"%llu",(unsigned long long)s->snapshot_version);else sb_cstr(&b,"null");
    sb_cstr(&b,",\"request_fingerprint\":");optional(&b,s?s->request_fingerprint:STR_EMPTY);
    sb_cstr(&b,",\"snapshot_fingerprint\":");optional(&b,identified?snapshot_identity(a,s):STR_EMPTY);
    sb_cstr(&b,",\"source_fingerprint\":");optional(&b,identified?hash256_str(a,identity_sources(a,sm)):STR_EMPTY);
    sb_cstr(&b,",\"compiler_fingerprint\":");optional(&b,compiler);sb_cstr(&b,",\"compiler_version\":");js(&b,version?version:"unknown");
    sb_cstr(&b,",\"binding_fingerprint\":null,\"artifact_fingerprint\":null,\"sources\":");
    if(identified)sb_str(&b,descriptors(a,s));else sb_cstr(&b,"[]");uint32_t identity_end=b.len;
    sb_cstr(&b,",\"location_encoding\":{\"offset_unit\":\"byte\",\"column_unit\":\"byte\",\"line_base\":1,\"column_base\":1},\"admission\":{\"target\":");if(s&&s->target>=ANALYZE_NATIVE&&s->target<=ANALYZE_REFERENCE)js(&b,target_name(s->target));else sb_cstr(&b,"null");
    sb_cstr(&b,",\"status\":");js(&b,admitted?"admitted":!strcmp(stage,"target_admission")?"unavailable":"not_checked");
    sb_cstr(&b,",\"scope\":\"complete_supplied_source_set\",\"enfusion_prefix\":\"BE\"},\"execution\":\"not_run\",\"engine_verification\":\"not_run\",\"diagnostics\":");
    sb_str(&b,diag_render_json(a,d));sb_cstr(&b,",\"limits\":{\"files\":64,\"file_bytes\":1048576,\"total_bytes\":8388608,\"total_tokens\":262144,\"json_bytes\":1048576,\"json_depth\":48,\"json_nodes\":16384,\"json_decoded_string_bytes\":1048576,\"json_work\":8388608},\"repair_guidance\":");
    js(&b,code==0?"Publish diagnostics only if request ID, document versions, source hashes and compiler identity still match the requesting client snapshot.":"Inspect stage and diagnostic byte spans. Supply every source as exact adjacent content bytes; no source discovery or disk fallback occurs. Target admission does not execute a program.");
    sb_char(&b,'}');Str json=sb_finish(&b);return(AnalyzeResult){json,status,stage,code,str_slice(json,identity_start,identity_end-identity_start)};
}
static void invalid(DiagBag *d,Span span,const char *message){Diag *x=diag_error(d,804,span,"%s",message);diag_help(x,"use the strict beryl.analysis.v1 schema and exact content hashes; analysis never reads logical source paths");}
static void pass_result(DiagBag *d,bool ok){if(!ok&&!diag_errors(d))invalid(d,SPAN_NONE,"compiler analysis pass did not complete successfully");}
static bool validate_snapshot(const AnalyzeSnapshot *s,DiagBag *d){
    if(!s||!token(s->request_id,128)||s->snapshot_version>ANALYZE_MAX_VERSION||s->target>ANALYZE_REFERENCE||s->target<ANALYZE_NATIVE||
        !s->sources||!s->source_count||s->source_count>ANALYZE_MAX_FILES||
        (s->request_fingerprint.len&&!hash_valid(s->request_fingerprint))||
        (s->expected_compiler_sha256.len&&!hash_valid(s->expected_compiler_sha256))){invalid(d,SPAN_NONE,"invalid analysis snapshot metadata");return false;}
    uint64_t total=0;
    for(uint32_t i=0;i<s->source_count;i++){
        const AnalyzeSource *f=&s->sources[i];
        if(!logical_path(f->path)||!hash_valid(f->sha256)||f->document_version>ANALYZE_MAX_VERSION||
            (f->text.len&&!f->text.ptr)||f->text.len>ANALYZE_MAX_FILE_BYTES){invalid(d,SPAN_NONE,"invalid source metadata or source byte limit exceeded");return false;}
        total+=f->text.len;if(total>ANALYZE_MAX_TOTAL_BYTES){invalid(d,SPAN_NONE,"analysis total source byte limit exceeded");return false;}
        for(uint32_t j=0;j<i;j++)if(folded_equal(f->path,s->sources[j].path)){invalid(d,SPAN_NONE,"duplicate logical source path (ASCII case-insensitive)");return false;}
    }
    return true;
}
AnalyzeResult analyze_snapshot(Arena *a,const AnalyzeSnapshot *s,const char *version){
    SourceMap *sm=srcmap_new(a);DiagBag *d=diag_new(a,sm);Str compiler=identity_compiler(a);
    if(!validate_snapshot(s,d))return result(a,NULL,sm,d,version,compiler,"failure","request_schema",1,false,false);
    if(s->expected_compiler_sha256.len&&(!compiler.len||!str_eq(compiler,s->expected_compiler_sha256))){invalid(d,SPAN_NONE,"expected compiler fingerprint does not match this analyzer");return result(a,s,sm,d,version,compiler,"stale_input","compiler_identity",2,false,false);}
    for(uint32_t i=0;i<s->source_count;i++){
        const AnalyzeSource *f=&s->sources[i];
        if(!str_eq(hash256_str(a,f->text),f->sha256)){invalid(d,SPAN_NONE,"source bytes do not match declared SHA-256");return result(a,s,sm,d,version,compiler,"stale_input","source_identity",2,false,false);}
        srcmap_add(sm,f->path,f->text);
    }
    for(uint32_t i=0;i<s->source_count;i++){
        const AnalyzeSource *f=&s->sources[i];uint32_t bad=0;const char *nul=f->text.len?memchr(f->text.ptr,0,f->text.len):NULL;
        if(nul||!json_utf8(f->text,&bad)){if(nul)bad=(uint32_t)(nul-f->text.ptr);invalid(d,(Span){i,bad,1},"Beryl source must be valid UTF-8 without NUL bytes");return result(a,s,sm,d,version,compiler,"failure","source_encoding",1,true,false);}
    }
    Program *p=prog_new(a);Interner *in=intern_new(a);uint64_t tokens=0;
    for(uint32_t i=0;i<s->source_count;i++){
        if(process_cancelled())return result(a,s,sm,d,version,compiler,"cancelled","cancelled",2,true,false);
        TokenVec ts=lex_file(a,sm,d,in,i);tokens+=ts.len;
        if(tokens>ANALYZE_MAX_TOKENS){invalid(d,(Span){i,0,0},"analysis aggregate token limit exceeded after lexing");return result(a,s,sm,d,version,compiler,"failure","resource_limit",1,true,false);}
        if(diag_errors(d))break;
        prog_add_module(p,parse_file(a,d,in,ts,i));if(diag_errors(d))break;
    }
    const char *stage="parse";
    if(!diag_errors(d)&&!process_cancelled()){stage="resolve";pass_result(d,resolve_program(d,p));}
    if(!diag_errors(d)&&!process_cancelled()){stage="type_check";pass_result(d,check_program(d,p));}
    if(!diag_errors(d)&&!process_cancelled()){stage="ownership";pass_result(d,ownership_check(d,p));}
    if(!diag_errors(d)&&!process_cancelled()){stage="taint";pass_result(d,taint_check(d,p,(SecurityOpts){s->forbid_unsafe}));}
    if(process_cancelled())return result(a,s,sm,d,version,compiler,"cancelled","cancelled",2,true,false);
    if(diag_errors(d))return result(a,s,sm,d,version,compiler,"failure",stage,1,true,false);
    bool ok=s->target==ANALYZE_NATIVE?native_lint(d,a,p):s->target==ANALYZE_REFERENCE?reference_admit(d,p):enfusion_lint(d,p,(EnfusionOpts){.prefix=STR_LIT("BE")});
    ok=ok&&!diag_errors(d);
    if(process_cancelled())return result(a,s,sm,d,version,compiler,"cancelled","cancelled",2,true,false);
    return result(a,s,sm,d,version,compiler,ok?"success":"unavailable","target_admission",ok?0:3,true,ok);
}

static Span at(const JsonValue *v){return v?(Span){0,v->offset,v->length}:SPAN_NONE;}
static bool members(const JsonValue *o,const char *const *names,uint32_t count,DiagBag *d){
    if(!o||o->kind!=JR_OBJECT){invalid(d,at(o),"expected JSON object");return false;}
    for(const JsonValue *v=o->child;v;v=v->next){bool known=false;for(uint32_t i=0;i<count;i++)if(str_eq_c(v->name,names[i]))known=true;
        if(!known){invalid(d,at(v),"unknown analysis request member");return false;}}
    return true;
}
static bool string_member(const JsonValue *o,const char *key,Str *out,DiagBag *d){JsonValue *v=json_member(o,key);if(!v||v->kind!=JR_STRING){invalid(d,at(v),"missing or non-string analysis request member");return false;}*out=v->text;return true;}
static bool integer_member(const JsonValue *o,const char *key,uint64_t max,uint64_t *out,DiagBag *d){JsonValue *v=json_member(o,key);if(!json_u64(v,max,out)){invalid(d,at(v),"missing or invalid unsigned decimal integer member");return false;}return true;}
AnalyzeResult analyze_request(Arena *a,Str request,AnalyzeRead reader,void *user,const char *version){
    SourceMap *sm=srcmap_new(a);DiagBag *d=diag_new(a,sm);
    /* Enforce the direct API's request-byte bound before hashing or constructing
     * SourceMap's line table, not only inside the JSON reader. */
    if((request.len&&!request.ptr)||request.len>json_read_limits().bytes){
        invalid(d,SPAN_NONE,"invalid request bytes or JSON byte limit exceeded");
        return result(a,NULL,sm,d,version,identity_compiler(a),"failure","request_parse",1,false,false);
    }
    srcmap_add(sm,STR_LIT("<analysis-request>"),request);
    AnalyzeSnapshot s={.target=(AnalyzeTarget)-1};s.request_fingerprint=hash256_str(a,request);JsonReadError error={0};
    JsonValue *root=json_read(a,request,json_read_limits(),&error);const char *stage="request_parse";
    if(!root){invalid(d,(Span){0,error.offset,error.offset<request.len?1u:0u},error.message);goto bad;}
    stage="request_schema";
    static const char *const fields[]={"schema_version","request_id","snapshot_version","target","forbid_unsafe","sources","expected_compiler_sha256"};
    static const char *const source_fields[]={"path","sha256","document_version","content_file"};
    uint64_t schema=0;Str target=STR_EMPTY;
    if(!members(root,fields,7,d)||!integer_member(root,"schema_version",1,&schema,d)||schema!=1||
        !string_member(root,"request_id",&s.request_id,d)||!integer_member(root,"snapshot_version",ANALYZE_MAX_VERSION,&s.snapshot_version,d)||
        !string_member(root,"target",&target,d))goto bad;
    if(str_eq_c(target,"native"))s.target=ANALYZE_NATIVE;else if(str_eq_c(target,"enfusion"))s.target=ANALYZE_ENFUSION;
    else if(str_eq_c(target,"reference"))s.target=ANALYZE_REFERENCE;else{invalid(d,at(json_member(root,"target")),"unknown analysis target");goto bad;}
    JsonValue *unsafe=json_member(root,"forbid_unsafe");if(!unsafe||unsafe->kind!=JR_BOOL){invalid(d,at(unsafe),"forbid_unsafe must be explicitly boolean");goto bad;}s.forbid_unsafe=unsafe->boolean;
    if(json_member(root,"expected_compiler_sha256")&&!string_member(root,"expected_compiler_sha256",&s.expected_compiler_sha256,d))goto bad;
    JsonValue *sources=json_member(root,"sources");
    if(!sources||sources->kind!=JR_ARRAY||!sources->count||sources->count>ANALYZE_MAX_FILES){invalid(d,at(sources),"sources must contain 1 through 64 entries");goto bad;}
    s.source_count=sources->count;s.sources=ARENA_ARRAY(a,AnalyzeSource,s.source_count);Str *names=ARENA_ARRAY(a,Str,s.source_count);
    uint32_t i=0;for(JsonValue *f=sources->child;f;f=f->next,i++){
        if(!members(f,source_fields,4,d)||!string_member(f,"path",&s.sources[i].path,d)||!string_member(f,"sha256",&s.sources[i].sha256,d)||
            !integer_member(f,"document_version",ANALYZE_MAX_VERSION,&s.sources[i].document_version,d)||!string_member(f,"content_file",&names[i],d))goto bad;
        if(!content_name(names[i])){invalid(d,at(json_member(f,"content_file")),"content_file must be a safe adjacent ASCII basename");goto bad;}
        for(uint32_t j=0;j<i;j++)if(folded_equal(names[i],names[j])){invalid(d,at(f),"duplicate content_file (ASCII case-insensitive)");goto bad;}
    }
    if(!validate_snapshot(&s,d))goto bad;
    if(s.expected_compiler_sha256.len){
        Str compiler=identity_compiler(a);
        if(!compiler.len||!str_eq(compiler,s.expected_compiler_sha256)){
            invalid(d,SPAN_NONE,"expected compiler fingerprint does not match this analyzer");
            return result(a,&s,sm,d,version,compiler,"stale_input","compiler_identity",2,false,false);
        }
    }
    if(!reader){invalid(d,SPAN_NONE,"no exact content reader supplied");goto bad;}
    /* Metadata is now wholly validated; only the declared basenames are read. */
    stage="source_read";
    uint64_t bytes=0;for(i=0;i<s.source_count;i++){
        if(process_cancelled())return result(a,&s,sm,d,version,identity_compiler(a),"cancelled","cancelled",2,false,false);
        if(!reader(user,a,names[i],&s.sources[i].text)){invalid(d,SPAN_NONE,"required content file unavailable, non-regular, linked, locked or oversized; no disk fallback");return result(a,&s,sm,d,version,identity_compiler(a),"failure","source_read",1,false,false);}
        bytes+=s.sources[i].text.len;if(s.sources[i].text.len>ANALYZE_MAX_FILE_BYTES||bytes>ANALYZE_MAX_TOTAL_BYTES){invalid(d,SPAN_NONE,"analysis source byte limit exceeded");goto bad;}
    }
    return analyze_snapshot(a,&s,version);
bad:
    if(!diag_errors(d))invalid(d,at(root),"unsupported analysis schema version");
    return result(a,&s,sm,d,version,identity_compiler(a),"failure",stage,1,false,false);
}

/* File handles are held for the entire request. Windows denies write/delete
 * sharing; POSIX uses directory-relative O_NOFOLLOW and an end-of-request byte
 * recheck. These are snapshot inputs, not permission to read arbitrary paths. */
#ifdef _WIN32
typedef HANDLE InputHandle;
#define INPUT_BAD INVALID_HANDLE_VALUE
#else
typedef int InputHandle;
#define INPUT_BAD (-1)
#endif
typedef struct {InputHandle handle;Str bytes;const char *name;} HeldInput;
typedef struct {Arena *arena;const char *directory;InputHandle parent;HeldInput held[ANALYZE_MAX_FILES+1];uint32_t count;} Inputs;
static void close_input(InputHandle h){if(h==INPUT_BAD)return;
#ifdef _WIN32
    CloseHandle(h);
#else
    close(h);
#endif
}
static InputHandle parent_open(Arena *a,const char *directory){
#ifdef _WIN32
    wchar_t *w=fs_wide(a,directory);if(!w)return INPUT_BAD;
    HANDLE h=CreateFileW(w,FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,NULL);
    BY_HANDLE_FILE_INFORMATION f;if(h!=INPUT_BAD&&(!GetFileInformationByHandle(h,&f)||!(f.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)||(f.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT))){CloseHandle(h);return INPUT_BAD;}return h;
#else
    (void)a;return open(directory,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
#endif
}
static InputHandle input_open(Inputs *in,const char *name,uint32_t limit,uint32_t *size){
#ifdef _WIN32
    const char *path=fs_join(in->arena,in->directory,name);wchar_t *w=fs_wide(in->arena,path);if(!w)return INPUT_BAD;
    HANDLE h=CreateFileW(w,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,NULL);
    BY_HANDLE_FILE_INFORMATION f;
    if(h==INPUT_BAD)return h;
    if(GetFileType(h)!=FILE_TYPE_DISK||!GetFileInformationByHandle(h,&f)||(f.dwFileAttributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))||f.nNumberOfLinks!=1||f.nFileSizeHigh||f.nFileSizeLow>limit){CloseHandle(h);return INPUT_BAD;}
    *size=f.nFileSizeLow;return h;
#else
    int h=openat(in->parent,name,O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK);struct stat f;
    if(h<0)return INPUT_BAD;
    if(fstat(h,&f)||!S_ISREG(f.st_mode)||f.st_nlink!=1||f.st_size<0||(uint64_t)f.st_size>limit){close(h);return INPUT_BAD;}
    *size=(uint32_t)f.st_size;return h;
#endif
}
static bool read_handle(Arena *a,InputHandle h,uint32_t size,Str *out){
#ifdef _WIN32
    LARGE_INTEGER zero;zero.QuadPart=0;if(!SetFilePointerEx(h,zero,NULL,FILE_BEGIN))return false;
#else
    if(lseek(h,0,SEEK_SET)<0)return false;
#endif
    char *bytes=ARENA_ARRAY(a,char,(size_t)size+1);uint32_t got=0;
    while(got<size){
#ifdef _WIN32
        DWORD n=0;if(!ReadFile(h,bytes+got,size-got,&n,NULL)||!n)return false;
#else
        ssize_t n=read(h,bytes+got,size-got);if(n<=0)return false;
#endif
        got+=(uint32_t)n;
    }
    char extra;
#ifdef _WIN32
    DWORD n=0;if(!ReadFile(h,&extra,1,&n,NULL)||n)return false;
#else
    if(read(h,&extra,1)!=0)return false;
#endif
    bytes[size]=0;*out=str_new(bytes,size);return true;
}
static bool load_input(Inputs *in,const char *name,uint32_t limit,Str *out){
    if(in->count>=ANALYZE_MAX_FILES+1)return false;uint32_t size=0;
    InputHandle h=input_open(in,name,limit,&size);if(h==INPUT_BAD)return false;
    if(!read_handle(in->arena,h,size,out)){close_input(h);return false;}
    in->held[in->count++]=(HeldInput){h,*out,name};return true;
}
static bool content_read(void *user,Arena *a,Str name,Str *bytes){Inputs *in=user;return load_input(in,str_cstr(a,name),ANALYZE_MAX_FILE_BYTES,bytes);}
static AnalyzeResult command_error(Arena *a,const char *version,const char *status,const char *stage,const char *message,int code){SourceMap *sm=srcmap_new(a);DiagBag *d=diag_new(a,sm);invalid(d,SPAN_NONE,message);return result(a,NULL,sm,d,version,identity_compiler(a),status,stage,code,false,false);}
static bool unchanged(Inputs *in,HeldInput *held){
#ifndef _WIN32
    struct stat before,now;
    if(fstat(held->handle,&before)||fstatat(in->parent,held->name,&now,AT_SYMLINK_NOFOLLOW)||
       !S_ISREG(now.st_mode)||before.st_dev!=now.st_dev||before.st_ino!=now.st_ino||now.st_nlink!=1)return false;
#endif
    Str bytes=STR_EMPTY;return read_handle(in->arena,held->handle,held->bytes.len,&bytes)&&str_eq(bytes,held->bytes);
}
/* Preserve correlation and inspected-byte identity when rejecting an otherwise
 * complete result. The nested result is explicitly rejected, never publishable. */
static AnalyzeResult rejected_result(Arena *a,AnalyzeResult previous,const char *status,const char *stage){
    SB b;sb_init(&b,a);sb_cstr(&b,"{\"schema_version\":1,\"operation\":\"analyze\",\"status\":");js(&b,status);sb_cstr(&b,",\"stage\":");js(&b,stage);
    sb_str(&b,previous.identity_fragment);
    sb_cstr(&b,",\"admission\":{\"status\":\"not_checked\"},\"execution\":\"not_run\",\"engine_verification\":\"not_run\",\"diagnostics\":[],\"repair_guidance\":\"Discard the rejected analysis. Submit a fresh immutable request matching current source versions.\",\"rejected_analysis\":");
    sb_str(&b,previous.json);sb_char(&b,'}');return(AnalyzeResult){sb_finish(&b),status,stage,2,previous.identity_fragment};
}
int analyze_command(int argc,char **argv,const char *version){
    process_install_signals();
    Arena *a=arena_new(0);const char *path=NULL;bool bad=false;
    for(int i=0;i<argc;i++){if(!strcmp(argv[i],"--request")&&!path&&i+1<argc)path=argv[++i];else bad=true;}
    AnalyzeResult r;Inputs in={.arena=a,.parent=INPUT_BAD};
    if(bad||!path||!*path){r=command_error(a,version,"failure","arguments","usage: beryl analyze --request <snapshot-directory/request.json>",1);goto done;}
    const char *absolute=fs_absolute(a,path);if(!absolute){r=command_error(a,version,"failure","request_read","cannot resolve request path",1);goto done;}
    const char *last=NULL;for(const char *p=absolute;*p;p++)if(*p=='/'||*p=='\\')last=p;
    if(!last||!last[1]){r=command_error(a,version,"failure","request_read","request must name a regular JSON file",1);goto done;}
    /* Keep the root separator on POSIX and drive roots on Windows. */
    uint32_t length=(uint32_t)(last-absolute);if(!length|| (length==2&&absolute[1]==':'))length++;
    in.directory=str_cstr(a,str_new(absolute,length));in.parent=parent_open(a,in.directory);
    Str request=STR_EMPTY;
    if(in.parent==INPUT_BAD||!load_input(&in,last+1,json_read_limits().bytes,&request)){r=command_error(a,version,"failure","request_read","request directory/file unavailable, linked, locked, non-regular or oversized",1);goto done;}
    r=analyze_request(a,request,content_read,&in,version);
    for(uint32_t i=0;i<in.count;i++)if(!unchanged(&in,&in.held[i])){r=rejected_result(a,r,"stale_input","source_recheck");break;}
    if(process_cancelled())r=rejected_result(a,r,"cancelled","cancelled");
done:
    for(uint32_t i=0;i<in.count;i++)close_input(in.held[i].handle);close_input(in.parent);
    int code=r.exit_code;if(fwrite(r.json.ptr,1,r.json.len,stdout)!=r.json.len||fputc('\n',stdout)==EOF||fflush(stdout)==EOF)code=2;
    arena_free(a);return code;
}
