#include "doctor.h"
#include "binding_context.h"
#include "features.h"
#include "manifest.h"
#include "process.h"
#include "../common/fs.h"
#include "../common/hash.h"
#include "../common/json.h"
#include <errno.h>
#include <stdlib.h>
#include <string.h>

/* Inventory never executes project or tool code. Bounded ASCII string maps
 * below recognize only the installed loader's identity files, not general JSON. */
typedef struct { Str key, value; } Pair;
typedef struct { Pair pairs[32]; size_t count; } StringMap;
typedef struct {
    const char *path, *status; Str sha;
} FileIdentity;
typedef struct {
    const char *root, *status, *reason; FileIdentity loader, active, manifest;
    Str declared, actual, files; bool contents_match;
} ToolInventory;
typedef struct {
    const char *name, *job, *status, *stage, *reason;
    Str source_hash, executable_hash, tool_before, tool_after;
    ProcessResult version, compile, run;
    bool version_attempted, compile_attempted, run_attempted;
    const char *const *version_argv, *const *compile_argv, *const *run_argv;
} Probe;
static const char *probe_source =
    "#include <stdio.h>\n"
    "int main(void) { volatile int x = 40; if (x + 2 != 42) return 9; "
    "return puts(\"BERYL_DOCTOR_NATIVE_V1\") < 0 ? 10 : 0; }\n";

static void js(SB *b,const char *s) { if (s) json_string(b,str_from(s)); else sb_cstr(b,"null"); }
static void optional(SB *b,Str s) { if (s.len) json_string(b,s); else sb_cstr(b,"null"); }
static Str hash_file(Arena *a,const char *path,uint64_t limit) {
    if (!path) return STR_EMPTY;
    FILE *f=fs_open(path,"rb"); if (!f) return STR_EMPTY;
    Hash256 hash; hash256_init(&hash); unsigned char block[16384]; size_t n; uint64_t total=0; bool ok=true;
    while ((n=fread(block,1,sizeof block,f))!=0) {
        if (n>limit-total) { ok=false; break; }
        total+=n; hash256_update(&hash,block,n);
    }
    if (ferror(f) || !total) ok=false;
    if (fclose(f)) ok=false;
    return ok ? hash256_finish(a,&hash) : STR_EMPTY;
}
static FileIdentity identify(Arena *a,const char *path,uint64_t limit) {
    FileIdentity f={path,"unavailable",STR_EMPTY};
    f.sha=hash_file(a,path,limit); if (f.sha.len) f.status="readable"; return f;
}
static Str small_file(Arena *a,const char *path,size_t maximum) {
    FILE *f=fs_open(path,"rb"); if (!f) return STR_EMPTY;
    bool ok=fseek(f,0,SEEK_END)==0; long size=ok ? ftell(f) : -1;
    ok=ok && size>0 && (unsigned long)size<=maximum && fseek(f,0,SEEK_SET)==0;
    char *bytes=NULL;
    if (ok) {
        bytes=arena_alloc(a,(size_t)size+1,1);
        ok=fread(bytes,1,(size_t)size,f)==(size_t)size && !ferror(f) && fgetc(f)==EOF && !ferror(f);
    }
    if (fclose(f)) ok=false;
    if (!ok) return STR_EMPTY;
    bytes[size]=0; return str_new(bytes,(uint32_t)size);
}
static void whitespace(Str data,size_t *at) {
    while (*at<data.len && (data.ptr[*at]==' ' || data.ptr[*at]=='\r' || data.ptr[*at]=='\n' || data.ptr[*at]=='\t')) (*at)++;
}
static bool quoted(Str data,size_t *at,Str *out) {
    whitespace(data,at); if (*at>=data.len || data.ptr[(*at)++]!='"') return false;
    size_t start=*at;
    while (*at<data.len && data.ptr[*at]!='"') {
        unsigned char ch=(unsigned char)data.ptr[*at];
        if (ch<32 || ch>126 || ch=='\\') return false;
        (*at)++;
    }
    if (*at>=data.len || *at-start>512) return false;
    *out=str_new(data.ptr+start,(uint32_t)(*at-start)); (*at)++; return true;
}
static bool string_map(Str data,StringMap *map) {
    memset(map,0,sizeof *map); size_t at=0; whitespace(data,&at);
    if (at>=data.len || data.ptr[at++]!='{') return false;
    whitespace(data,&at);
    if (at<data.len && data.ptr[at]=='}') { at++; whitespace(data,&at); return at==data.len; }
    for (;;) {
        if (map->count==32) return false;
        Pair *p=&map->pairs[map->count];
        if (!quoted(data,&at,&p->key)) return false;
        whitespace(data,&at); if (at>=data.len || data.ptr[at++]!=':') return false;
        if (!quoted(data,&at,&p->value)) return false;
        for (size_t j=0;j<map->count;j++) if (str_eq(p->key,map->pairs[j].key)) return false;
        map->count++; whitespace(data,&at); if (at>=data.len) return false;
        if (data.ptr[at]=='}') { at++; whitespace(data,&at); return at==data.len; }
        if (data.ptr[at++]!=',') return false;
    }
}
static bool digest(Str s) {
    if (s.len!=64) return false;
    for (uint32_t i=0;i<s.len;i++) if (!((s.ptr[i]>='a' && s.ptr[i]<='f') || (s.ptr[i]>='0' && s.ptr[i]<='9'))) return false;
    return true;
}
static const char *tool_files[] = {
    "mod.py", "process_job.py", "engine-compile.ps1", "beryl.mod.v1.schema.json",
    "scenarios.py", "map-cursor.c.in", "scenario-engine-run.ps1", "source_maps.py",
    "terrain_scenarios.py", "terrain-reference.c.txt", "terrain-reference.json", "terrain-adapter.c.in", "terrain-handler.c.in",
    "storage_scenarios.py", "array-storage.c.in", "canvas-retention.c.in",
    "terrain_measurements.py", "terrain-measurement.c.in", "terrain-adapter-v1.c.txt",
    "mcp_server.py", "beryl.analysis.v1.schema.json",
    /* Exact newer installed profiles extend the historical prefix sets. */
    "component_contracts.py", "tablet-component-contracts.v1.json", "beryl.mod.v2.schema.json",
    "component_generation.py"
};
static int pair_order(const void *a,const void *b) {
    const Pair *x=a,*y=b; size_t n=x->key.len<y->key.len?x->key.len:y->key.len;
    int c=memcmp(x->key.ptr,y->key.ptr,n); return c ? c : (x->key.len>y->key.len)-(x->key.len<y->key.len);
}
static ToolInventory inspect_tools(Arena *a,const char *root) {
    ToolInventory t={0}; t.root=root; t.status="unavailable"; t.reason="Installed loader or identity files are missing or unreadable.";
    if (!root) return t;
    const char *loader=fs_join(a,root,"mod.py"),*active=fs_join(a,root,"active.json");
    t.loader=identify(a,loader,1024*1024); t.active=identify(a,active,4096);
    if (!t.loader.sha.len || !t.active.sha.len) return t;
    StringMap m; Str active_bytes=small_file(a,active,4096);
    if (!string_map(active_bytes,&m) || m.count!=1 || !str_eq_c(m.pairs[0].key,"bundle") || !digest(m.pairs[0].value)) {
        t.status="failure"; t.reason="The active pointer is not the bounded installed identity format."; return t;
    }
    t.declared=m.pairs[0].value;
    const char *dir=fs_join(a,root,str_cstr(a,t.declared));
    const char *manifest=fs_join(a,dir,"bundle.json"); t.manifest=identify(a,manifest,65536);
    if (!t.manifest.sha.len) return t;
    Str bytes=small_file(a,manifest,65536);
    if (!string_map(bytes,&m)) { t.status="failure"; t.reason="The bundle manifest is malformed or exceeds the bounded string-map format."; return t; }
    if (m.count!=4 && m.count!=8 && m.count!=13 && m.count!=16 && m.count!=19 && m.count!=21 && m.count!=24 && m.count!=25) {
        t.reason="The installed bundle file-set version is outside this inventory reader."; return t;
    }
    for (size_t i=0;i<m.count;i++) {
        bool found=false;
        for (size_t j=0;j<m.count;j++) if (str_eq_c(m.pairs[i].key,tool_files[j])) found=true;
        if (!found || !digest(m.pairs[i].value)) { t.status="failure"; t.reason="The bundle has an unknown filename or malformed content hash."; return t; }
    }
    qsort(m.pairs,m.count,sizeof(Pair),pair_order);
    SB file_records,canonical; sb_init(&file_records,a); sb_init(&canonical,a);
    sb_char(&file_records,'['); sb_char(&canonical,'{'); bool matches=true;
    for (size_t i=0;i<m.count;i++) {
        Pair p=m.pairs[i]; const char *path=fs_join(a,dir,str_cstr(a,p.key));
        Str actual=hash_file(a,path,16*1024*1024); if (!actual.len || !str_eq(actual,p.value)) matches=false;
        if (i) { sb_char(&file_records,','); sb_char(&canonical,','); }
        sb_cstr(&file_records,"{\"name\":"); json_string(&file_records,p.key);
        sb_cstr(&file_records,",\"expected_sha256\":"); json_string(&file_records,p.value);
        sb_cstr(&file_records,",\"actual_sha256\":"); optional(&file_records,actual); sb_char(&file_records,'}');
        json_string(&canonical,p.key); sb_char(&canonical,':'); optional(&canonical,actual);
    }
    sb_char(&file_records,']'); sb_char(&canonical,'}'); t.files=sb_finish(&file_records);
    t.actual=hash256_str(a,sb_finish(&canonical));
    bool stable=str_eq(hash_file(a,loader,1024*1024),t.loader.sha) && str_eq(hash_file(a,active,4096),t.active.sha) &&
        str_eq(hash_file(a,manifest,65536),t.manifest.sha);
    t.contents_match=matches && stable && str_eq(t.actual,t.declared);
    t.status=t.contents_match ? "content_match" : "stale_input";
    t.reason=t.contents_match ? "Observed selected file bytes match the declared bundle. Loader recognition, link policy, Python compatibility and dispatch execution are not verified." : "Installed file bytes or metadata changed or differ from the active content identity.";
    return t;
}
static void file_json(SB *b,FileIdentity f) {
    sb_cstr(b,"{\"path\":"); js(b,f.path); sb_cstr(b,",\"status\":"); js(b,f.status);
    sb_cstr(b,",\"sha256\":"); optional(b,f.sha); sb_cstr(b,",\"execution\":\"not_run\"}");
}
static void tool_json(SB *b,ToolInventory t) {
    sb_cstr(b,"{\"root\":"); js(b,t.root); sb_cstr(b,",\"status\":"); js(b,t.status); sb_cstr(b,",\"reason\":"); js(b,t.reason);
    sb_cstr(b,",\"loader\":"); file_json(b,t.loader); sb_cstr(b,",\"active\":"); file_json(b,t.active);
    sb_cstr(b,",\"manifest\":"); file_json(b,t.manifest); sb_cstr(b,",\"declared_bundle_sha256\":"); optional(b,t.declared);
    sb_cstr(b,",\"observed_bundle_sha256\":"); optional(b,t.actual); sb_cstr(b,",\"files\":"); sb_str(b,t.files.len?t.files:STR_LIT("[]"));
    sb_cstr(b,",\"loader_recognition\":\"not_checked\",\"link_policy\":\"not_checked\",\"dispatch_execution\":\"not_run\"}");
}
static void argv_json(SB *b,const char *const *argv) {
    if (!argv) { sb_cstr(b,"null"); return; }
    sb_char(b,'['); for (size_t i=0;argv[i];i++) { if (i) sb_char(b,','); js(b,argv[i]); } sb_char(b,']');
}
static void process_json(SB *b,ProcessResult p,bool attempted,const char *const *argv) {
    if (!attempted) { sb_cstr(b,"null"); return; }
    sb_cstr(b,"{\"status\":"); js(b,process_status_name(p.status)); sb_cstr(b,",\"exit_code\":");
    if (p.status==PROCESS_EXITED) sb_fmt(b,"%u",p.exit_code); else sb_cstr(b,"null");
    sb_fmt(b,",\"os_error\":%u,\"argv\":",p.os_error); argv_json(b,argv);
    sb_cstr(b,",\"stdout_log\":"); js(b,p.stdout_path); sb_cstr(b,",\"stderr_log\":"); js(b,p.stderr_path);
    sb_cstr(b,",\"stdout\":"); json_string(b,p.out); sb_cstr(b,",\"stderr\":"); json_string(b,p.err); sb_char(b,'}');
}
static bool successful(ProcessResult p) { return p.status==PROCESS_EXITED && p.exit_code==0; }
static const char *failed_status(ProcessResult p) { return p.status==PROCESS_EXITED ? "failure" : process_status_name(p.status); }
static void probe_json(SB *b,const Probe *p) {
    sb_cstr(b,"{\"name\":"); js(b,p->name); sb_cstr(b,",\"status\":"); js(b,p->status); sb_cstr(b,",\"stage\":"); js(b,p->stage);
    sb_cstr(b,",\"reason\":"); js(b,p->reason); sb_cstr(b,",\"job\":"); js(b,p->job);
    sb_cstr(b,",\"source_sha256\":"); optional(b,p->source_hash); sb_cstr(b,",\"artifact_sha256\":"); optional(b,p->executable_hash);
    sb_cstr(b,",\"tool_before_sha256\":"); optional(b,p->tool_before); sb_cstr(b,",\"tool_after_sha256\":"); optional(b,p->tool_after);
    sb_cstr(b,",\"tool_version\":"); process_json(b,p->version,p->version_attempted,p->version_argv);
    sb_cstr(b,",\"compile\":"); process_json(b,p->compile,p->compile_attempted,p->compile_argv);
    sb_cstr(b,",\"run\":"); process_json(b,p->run,p->run_attempted,p->run_argv);
    sb_cstr(b,",\"scope\":\"fixed C11 compile-and-run readiness; not Beryl semantic or performance validation\",\"measurements\":null}");
}
static Probe native_probe(Arena *a,FileIdentity tool,const char *job_root,uint32_t timeout) {
    Probe p={.name="native",.status="unavailable",.stage="capability",.reason="Selected native compiler is missing or unreadable.",.tool_before=tool.sha};
    if (!tool.sha.len) return p;
    p.job=fs_job_dir(a,job_root);
    if (!p.job) { p.status="io_failure"; p.stage="job_directory"; p.reason="Cannot create an exclusive probe job directory; no launch attempted."; return p; }
    const char *source=fs_join(a,p.job,"probe.c");
#ifdef _WIN32
    const char *executable=fs_join(a,p.job,"probe.exe");
#else
    const char *executable=fs_join(a,p.job,"probe");
#endif
    Str code=str_from(probe_source); p.source_hash=hash256_str(a,code);
    if (!fs_write(source,code) || !str_eq(hash_file(a,source,4096),p.source_hash)) {
        p.status="io_failure"; p.stage="source_write"; p.reason="The fixed probe source could not be written and read back exactly."; return p;
    }
    const char **version=arena_alloc(a,3*sizeof(char *),_Alignof(char *)); version[0]=tool.path; version[1]="--version"; version[2]=NULL; p.version_argv=version;
    const char **compile=arena_alloc(a,11*sizeof(char *),_Alignof(char *));
    const char *args[]={tool.path,"-std=c11","-O0","-ffp-contract=off","-fno-fast-math","-Wall","-Werror",source,"-o",executable,NULL};
    memcpy(compile,args,sizeof args); p.compile_argv=compile;
    const char **run=arena_alloc(a,2*sizeof(char *),_Alignof(char *)); run[0]=executable; run[1]=NULL; p.run_argv=run;
    SB plan; sb_init(&plan,a); sb_cstr(&plan,"{\"schema_version\":1,\"operation\":\"doctor.native\",\"source_sha256\":"); json_string(&plan,p.source_hash);
    sb_cstr(&plan,",\"tool_sha256\":"); json_string(&plan,tool.sha); sb_fmt(&plan,",\"timeout_ms_per_process\":%u,\"steps\":[",timeout);
    argv_json(&plan,version); sb_char(&plan,','); argv_json(&plan,compile); sb_char(&plan,','); argv_json(&plan,run); sb_cstr(&plan,"]}\n");
    if (!fs_write(fs_join(a,p.job,"plan.json"),sb_finish(&plan))) { p.status="io_failure"; p.stage="plan_write"; p.reason="Cannot retain exact probe arguments before launch."; return p; }
    p.stage="tool_version"; p.version_attempted=true;
    p.version=process_run(a,(ProcessOpts){.argv=version,.cwd=p.job,.log_dir=p.job,.log_name="version",.timeout_ms=timeout});
    if (!successful(p.version)) { p.status=failed_status(p.version); p.reason="Selected tool identity process did not succeed."; goto finish; }
    if (!p.version.out.len && !p.version.err.len) { p.status="failure"; p.reason="Selected tool returned no version output."; goto finish; }
    p.stage="compile"; p.compile_attempted=true;
    p.compile=process_run(a,(ProcessOpts){.argv=compile,.cwd=p.job,.log_dir=p.job,.log_name="compile",.timeout_ms=timeout});
    if (!successful(p.compile)) { p.status=failed_status(p.compile); p.reason="The fixed C11 compilation did not succeed."; goto finish; }
    p.executable_hash=hash_file(a,executable,64*1024*1024);
    if (!p.executable_hash.len) { p.status="failure"; p.reason="Compiler success produced no readable nonempty executable; nothing was run."; goto finish; }
    p.stage="run"; p.run_attempted=true;
    p.run=process_run(a,(ProcessOpts){.argv=run,.cwd=p.job,.log_dir=p.job,.log_name="run",.timeout_ms=timeout});
    if (!successful(p.run)) { p.status=failed_status(p.run); p.reason="The freshly built probe did not execute successfully."; goto finish; }
    if ((!str_eq_c(p.run.out,"BERYL_DOCTOR_NATIVE_V1\n") && !str_eq_c(p.run.out,"BERYL_DOCTOR_NATIVE_V1\r\n")) || p.run.err.len) {
        p.status="failure"; p.reason="Probe output does not match the fixed expected observation."; goto finish;
    }
    p.status="success"; p.stage="complete"; p.reason="The selected compiler built and executed the fixed C11 probe in its owned directory.";
finish:
    p.tool_after=hash_file(a,tool.path,1024ULL*1024*1024);
    if (!str_eq(p.tool_after,p.tool_before) || !str_eq(hash_file(a,source,4096),p.source_hash) ||
        (p.executable_hash.len && !str_eq(hash_file(a,executable,64*1024*1024),p.executable_hash))) {
        p.status="stale_input"; p.reason="A selected tool, fixed source or produced executable changed during the probe.";
    }
    return p;
}
static const char *sibling(Arena *a,const char *exe,const char *name) {
    if (!exe) return NULL;
    size_t n=strlen(exe); while (n && exe[n-1]!='/' && exe[n-1]!='\\') n--;
    return fs_join(a,str_cstr(a,str_new(exe,(uint32_t)n)),name);
}
static const char *setting(Arena *a,DiagBag *d,const char *explicit_value,const char *variable,const char *fallback) {
    if (explicit_value) return explicit_value;
    const char *env=NULL;
    if (!process_environment(a,variable,&env)) {
        diag_error(d,804,SPAN_NONE,"cannot read %s as bounded UTF-8 configuration",variable);
        return NULL;
    }
    return env && *env ? env : fallback;
}
int doctor_command(int argc,char **argv,const char *compiler_version) {
    Arena *a=arena_new(0); SourceMap *sm=srcmap_new(a); DiagBag *d=diag_new(a,sm);
    const char *clang=NULL,*python=NULL,*tool_dir=NULL,*engine=NULL,*api=NULL,*project=NULL,*probe_name=NULL,*job_root=NULL,*format=NULL,*time_arg=NULL;
    uint32_t timeout=30000;
    const char *mod_override=setting(a,d,NULL,"BERYL_MOD_TOOL",NULL);
    for (int i=0;i<argc;i++) {
        const char **to=!strcmp(argv[i],"--clang")?&clang:!strcmp(argv[i],"--python")?&python:!strcmp(argv[i],"--tool-dir")?&tool_dir:
            !strcmp(argv[i],"--engine-executable")?&engine:!strcmp(argv[i],"--api-root")?&api:!strcmp(argv[i],"--project")?&project:
            !strcmp(argv[i],"--probe")?&probe_name:!strcmp(argv[i],"--job-root")?&job_root:!strcmp(argv[i],"--format")?&format:
            !strcmp(argv[i],"--timeout-ms")?&time_arg:NULL;
        if (!to) { diag_error(d,804,SPAN_NONE,"unknown doctor option `%s`",argv[i]); continue; }
        if (*to || i+1>=argc || !argv[i+1][0]) { diag_error(d,804,SPAN_NONE,"doctor option `%s` requires one nonempty value and cannot repeat",argv[i]); continue; }
        *to=argv[++i];
    }
    if (format && strcmp(format,"json") && strcmp(format,"text")) diag_error(d,804,SPAN_NONE,"doctor format must be json or text");
    if (probe_name && strcmp(probe_name,"native") && strcmp(probe_name,"enfusion-compile")) diag_error(d,804,SPAN_NONE,"doctor probe must be native or enfusion-compile");
    if ((job_root || time_arg) && (!probe_name || strcmp(probe_name,"native"))) diag_error(d,804,SPAN_NONE,"doctor job-root and timeout require the explicit native probe");
    if (time_arg) {
        char *end=NULL; errno=0; unsigned long value=strtoul(time_arg,&end,10);
        if (errno || !*time_arg || *time_arg<'0' || *time_arg>'9' || *end || !value || value>120000)
            diag_error(d,804,SPAN_NONE,"doctor timeout must be 1..120000 milliseconds per process");
        else timeout=(uint32_t)value;
    }
    bool json=format && !strcmp(format,"json");
    const char *exe=fs_executable(a); FileIdentity self={0},native={0},py={0}; ToolInventory tools={0};
    Manifest manifest={0}; BindingContext binding={0}; Probe probe={0}; const char *root=NULL;
    const char *status=diag_errors(d)?"failure":"success",*stage=diag_errors(d)?"arguments":"inventory";
    if (!diag_errors(d)) {
        root=fs_absolute(a,project?project:".");
        if (!root) diag_error(d,804,SPAN_NONE,"cannot resolve doctor project directory");
        else manifest=manifest_load(a,d,root);
        self=identify(a,exe,1024ULL*1024*1024);
        native=identify(a,process_find_executable(a,setting(a,d,clang,"BERYL_CLANG","clang")),1024ULL*1024*1024);
        py=identify(a,process_find_executable(a,setting(a,d,python,"BERYL_PYTHON","python")),1024ULL*1024*1024);
        tools=inspect_tools(a,tool_dir?fs_absolute(a,tool_dir):sibling(a,exe,"beryl-tools"));
        if (engine || api) binding=binding_context(a,"Math",engine?fs_absolute(a,engine):NULL,api?fs_absolute(a,api):NULL);
        if (diag_errors(d)) { status="failure"; stage="manifest"; }
        else if (!self.sha.len) { status="unavailable"; stage="compiler_identity"; }
        else if (probe_name && !strcmp(probe_name,"native")) {
            probe=native_probe(a,native,job_root?job_root:".beryl-cache",timeout); status=probe.status; stage="native_probe";
        } else if (probe_name) {
            probe=(Probe){.name="enfusion-compile",.status="unavailable",.stage="capability",.reason="Doctor does not yet dispatch the existing artifact-bound Workbench compile pipeline. Use beryl mod build and mod verify --stage compile with an explicit artifact."};
            status=probe.status; stage="capability";
        }
    }
    SB result; sb_init(&result,a); sb_cstr(&result,"{\"schema_version\":1,\"operation\":\"doctor\",\"stage\":"); js(&result,stage);
    sb_cstr(&result,",\"status\":"); js(&result,status); sb_cstr(&result,",\"compiler_version\":"); js(&result,compiler_version);
    sb_cstr(&result,",\"required_capability\":"); js(&result,probe_name?(!strcmp(probe_name,"native")?"clang.c11.compile_run":"enfusion.artifact_compile"):NULL);
    sb_cstr(&result,",\"compiler_fingerprint\":"); optional(&result,self.sha); sb_cstr(&result,",\"catalogue_fingerprint\":"); json_string(&result,features_fingerprint(a));
    sb_cstr(&result,",\"binding_fingerprint\":"); optional(&result,binding.fingerprint);
    sb_cstr(&result,",\"source_fingerprint\":null,\"artifact_fingerprint\":"); optional(&result,probe.executable_hash);
    sb_cstr(&result,",\"project\":{\"path\":"); js(&result,root); sb_fmt(&result,",\"manifest_found\":%s,\"manifest_sha256\":",manifest.found?"true":"false");
    optional(&result,manifest.found?hash256_str(a,manifest.source_text):STR_EMPTY);
    sb_cstr(&result,",\"source_admission\":\"not_checked\",\"guidance\":\"Use beryl context project or check for actual source-set admission.\"},\"inventory\":{\"compiler\":"); file_json(&result,self);
    sb_cstr(&result,",\"native_compiler\":"); file_json(&result,native); sb_cstr(&result,",\"python_optional\":"); file_json(&result,py);
    sb_cstr(&result,",\"installed_mod_tool\":"); tool_json(&result,tools);
    sb_cstr(&result,",\"configured_mod_tool_override\":"); js(&result,mod_override);
    sb_cstr(&result,",\"binding_snapshot\":"); if (binding.data.len) sb_str(&result,binding.data); else sb_cstr(&result,"null");
    sb_cstr(&result,",\"binding_check_status\":"); js(&result,binding.status?binding.status:"not_checked");
    sb_cstr(&result,",\"binding_check_scope\":\"Math document and optionally exact engine executable only; not all API documents\",\"native_dependencies\":\"not_checked\",\"python_version\":\"not_checked\",\"job_writability\":");
    js(&result,probe.job?"owned_directory_created":"not_checked");
    sb_cstr(&result,"},\"probe\":"); if (probe.name) probe_json(&result,&probe); else sb_cstr(&result,"null");
    sb_cstr(&result,",\"evidence_path\":"); const char *report_path=probe.job?fs_join(a,probe.job,"result.json"):NULL; js(&result,report_path);
    sb_cstr(&result,",\"program_execution\":"); js(&result,probe.run_attempted?"fixed_native_probe_attempted":"not_run");
    sb_cstr(&result,",\"engine_execution\":\"not_run\",\"measurements\":null,\"diagnostics\":"); sb_str(&result,diag_render_json(a,d));
    sb_cstr(&result,",\"guidance\":[\"Inventory success means the inspection completed; optional missing tools and stale identity checks remain visible in their own fields.\",\"Readable means file identity only, not executable or toolchain readiness.\",\"Set BERYL_CLANG or --clang to the intended compiler, then request --probe native to test compilation and execution.\",\"Python and the mod tool are optional for ordinary C11 compilation. Inventory never executes either.\",\"Use exact installed-tool and binding evidence before engine work; doctor never starts or stops an editor.\",\"No installation, ACL adjustment, retry, generated-code edit or active artifact promotion is performed.\"]}\n");
    Str output=sb_finish(&result); int code=!strcmp(status,"success")?0:!strcmp(status,"unavailable")?3:!strcmp(status,"failure")?1:2;
    if (report_path && !fs_write(report_path,output)) {
        code=2;
        /* Never emit a success envelope when retaining its required receipt fails. */
        SB failed; sb_init(&failed,a); sb_cstr(&failed,"{\"schema_version\":1,\"operation\":\"doctor\",\"stage\":\"receipt_write\",\"status\":\"io_failure\",\"evidence_path\":"); js(&failed,report_path);
        sb_cstr(&failed,",\"engine_execution\":\"not_run\",\"measurements\":null,\"completed_probe\":"); probe_json(&failed,&probe); sb_cstr(&failed,"}\n"); output=sb_finish(&failed);
    }
    if (json) {
        if (fwrite(output.ptr,1,output.len,stdout)!=output.len || fflush(stdout)) code=2;
    } else {
        printf("Beryl doctor: %s (%s)\n",code==2 && report_path ? "see receipt/output status" : status,stage);
        if (!diag_errors(d)) {
            printf("Native compiler: %s%s%s\n",native.status,native.path?" - ":"",native.path?native.path:"");
            printf("Python (optional): %s\nInstalled mod bundle: %s\n",py.status,tools.status);
            if (binding.status) printf("Selected engine/Math snapshot: %s\n",binding.status);
            if (probe.name) printf("Probe %s: %s - %s\n",probe.name,probe.status,probe.reason);
            else puts("Inventory only; compilation, source admission and engine execution were not run.");
            if (report_path) printf("Evidence: %s\n",report_path);
            puts("Use --format json for identities, individual checks and repair guidance.");
        } else diag_render(d,stderr,false);
        if (fflush(stdout)) code=2;
    }
    arena_free(a); return code;
}
