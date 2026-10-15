#include "reference_driver.h"
#include "identity.h"
#include "../common/fs.h"
#include "../common/hash.h"
#include "../common/json.h"
#include "../ir/c_emit.h"
#include <string.h>

static bool expected_number(const char **cursor,uint32_t *out,char end) {
    const char *p=*cursor; uint32_t n=0;
    if (*p<'0' || *p>'9') return false;
    do {
        uint32_t digit=(uint32_t)(*p-'0');
        if (n>(UINT32_MAX-digit)/10) return false;
        n=n*10+digit; p++;
    } while (*p>='0' && *p<='9');
    if (*p!=end) return false;
    *out=n; *cursor=end?p+1:p; return true;
}
bool driver_parse_expected_trap(const char *text,RefExpectedTrap *out) {
    if (!text || !out) return false;
    RefExpectedTrap value={.enabled=true}; const char *p;
    if (!strncmp(text,"overflow@",9)) { value.kind=REF_SOURCE_TRAP_OVERFLOW; p=text+9; }
    else if (!strncmp(text,"division_by_zero@",17)) { value.kind=REF_SOURCE_TRAP_DIV_ZERO; p=text+17; }
    else if (!strncmp(text,"bounds@",7)) { value.kind=REF_SOURCE_TRAP_BOUNDS; p=text+7; }
    else return false;
    if (!expected_number(&p,&value.file,':') || !expected_number(&p,&value.offset,'\0')) return false;
    if (value.file==UINT32_MAX) return false;
    *out=value; return true;
}
bool driver_parse_watch_root(const char *text,RefWatchRoot *out) {
    if (!text || !out) return false;
    RefWatchRoot value={.enabled=true}; const char *p=text;
    if (!expected_number(&p,&value.file,':') || !expected_number(&p,&value.offset,'\0') || value.file==UINT32_MAX) return false;
    *out=value; return true;
}

static bool expected_outcome(RefExpectedTrap expected,RefResult actual) {
    return expected.enabled && actual.status==REF_TRAP && actual.trap_trace_complete &&
        actual.trap_kind==expected.kind && actual.trap_span.file==expected.file &&
        actual.trap_span.offset==expected.offset && actual.failed_tests==0;
}
/* Native stderr retains the exact JSONL trace followed by the ordinary source
 * diagnostic. The complete reference prefix includes its terminal trap event;
 * a crash message, partial marker or additional JSON event cannot substitute. */
static bool trap_trace_matches(Str reference,Str native,RefTrapKind kind) {
    if (!reference.len || native.len<reference.len || memcmp(reference.ptr,native.ptr,reference.len)) return false;
    const char *prefix=kind==REF_SOURCE_TRAP_OVERFLOW ? "beryl: arithmetic overflow on " :
        kind==REF_SOURCE_TRAP_DIV_ZERO ? "beryl: division by zero at " : "beryl: index ";
    size_t plen=strlen(prefix); Str rest={native.ptr+reference.len,native.len-reference.len};
    if (rest.len<plen || memcmp(rest.ptr,prefix,plen) || !memchr(rest.ptr,'\n',rest.len)) return false;
    for (uint32_t i=0;i+9<rest.len;i++)
        if ((i==0 || rest.ptr[i-1]=='\n') && !memcmp(rest.ptr+i,"{\"event\":",9)) return false;
    return true;
}

int driver_reference_tests(Arena *a,SourceMap *sm,DiagBag *d,Program *p,
                        RefOpts opts,BuildOpts native,bool differential) {
    Str sources=identity_sources(a,sm),source_hash=hash256_str(a,sources),compiler=identity_compiler(a);
    bool use_ir = differential && native.requested_lowering && !strcmp(native.requested_lowering,"ir");
    bool ir_admitted = !use_ir;
    Str ir_source_hash = STR_EMPTY, ir_c_hash = STR_EMPTY;
    if (use_ir) {
        native.ir_tests = ir_lower(a,d,sm,p);
        if (native.ir_tests) {
            IrCResult emitted = ir_emit_c(a,native.ir_tests,(IrCOpts){.trace_tests=true});
            if (emitted.ok) {
                ir_admitted = true;
                ir_source_hash = native.ir_tests->source_manifest_sha256;
                ir_c_hash = hash256_str(a,emitted.source);
            } else diag_error(d,1101,emitted.error,"IR differential-test emission unavailable: %s",emitted.reason);
        }
    }
    const char *job=fs_job_dir(a,".beryl-cache");
    if (!job) { diag_error(d,1004,SPAN_NONE,"cannot create an isolated reference job"); return 2; }
    const char *out_path=fs_join(a,job,"reference.stdout.log");
    const char *events_path=fs_join(a,job,"reference.events.jsonl");
    FILE *out=fs_open(out_path,"wb"),*events=fs_open(events_path,"wb");
    RefResult result={.status=REF_IO};
    opts.output=out; opts.events=events;
    opts.cancelled=process_cancelled; opts.clock_ms=process_clock_ms; opts.timeout_ms=native.timeout_ms;
    bool reference_attempted = false;
    if (out && events && !ir_admitted) {
        result.status=REF_UNAVAILABLE;
        for (Diag *error=diag_first(d); error; error=error->next)
            if (error->level==DIAG_ERROR && error->code!=1101) result.status=REF_FAILED;
    }
    else if (out && events) { reference_attempted=true; result=reference_test(d,p,opts); }
    else diag_error(d,1004,SPAN_NONE,"cannot open reference output captures");
    int out_close=out?fclose(out):0, event_close=events?fclose(events):0;
    if (out_close || event_close) { result.status=REF_IO; diag_error(d,1004,SPAN_NONE,"cannot close reference output captures"); }
    Str output=STR_EMPTY,reference_events=STR_EMPTY;
    if (!fs_read(a,out_path,&output) || !fs_read(a,events_path,&reference_events)) {
        result.status=REF_IO; diag_error(d,1004,SPAN_NONE,"cannot read complete reference output captures");
    }
    bool expected=opts.expected_trap.enabled;
    bool ok=expected ? expected_outcome(opts.expected_trap,result) : result.status==REF_SUCCESS;
    if (expected && !differential) {
        diag_error(d,1006,SPAN_NONE,"expected source traps require differential verification"); ok=false;
    }
    if (expected && !ok && result.status!=REF_UNAVAILABLE && result.status!=REF_TIMEOUT && result.status!=REF_CANCELLED)
        diag_error(d,1006,result.trap_kind?result.trap_span:SPAN_NONE,
            "expected source trap %s at %u:%u was not observed completely; program outcome is %s",
            reference_trap_kind_name(opts.expected_trap.kind),opts.expected_trap.file,opts.expected_trap.offset,
            reference_status_name(result.status));
    bool compared=false;
    bool native_attempted=false, launch_attempted=false;
    bool native_trap_verified=false;
    BuildResult built={0}; ProcessResult run={.status=PROCESS_START_FAILED};
    if (ok && differential) {
        native_attempted=true;
        native.mode=CGEN_TRACE_TESTS; native.out_exe=NULL; native.cache_dir=job;
        native.trace_watch=(CgenTraceWatch){.enabled=opts.watch_root.enabled,
            .file=opts.watch_root.file,.offset=opts.watch_root.offset};
        ok=build_native(a,sm,d,p,native,&built);
        if (ok) {
            launch_attempted=true;
            const char *argv[]={built.exe,NULL};
            run=process_run(a,(ProcessOpts){.argv=argv,.log_dir=built.job_dir,.log_name="differential",.timeout_ms=native.timeout_ms});
            ok=run.status==PROCESS_EXITED && (expected ? run.exit_code!=0 : run.exit_code==0);
            if (!ok && run.status==PROCESS_EXITED)
                diag_error(d,1006,SPAN_NONE,"native differential execution failed with exit %u",run.exit_code);
            else if (!ok)
                diag_error(d,1006,SPAN_NONE,"native differential execution did not complete (%s, OS error %u)",process_status_name(run.status),run.os_error);
            else {
                compared=true;
                ok=str_eq(output,run.out) && reference_events.len>0 &&
                    (expected ? trap_trace_matches(reference_events,run.err,result.trap_kind) : str_eq(reference_events,run.err));
                native_trap_verified=expected && ok;
                if (!ok) diag_error(d,1006,SPAN_NONE,"native/reference outputs or ordered events differ; inspect the retained job logs");
            }
        }
    }
    if ((ok || !differential) && output.len && fwrite(output.ptr,1,output.len,stdout)!=output.len) {
        ok=false; diag_error(d,1004,SPAN_NONE,"cannot forward reference output");
    }
    SB report; sb_init(&report,a);
    sb_cstr(&report,"{\"schema_version\":1,\"operation\":\"test\",\"backend\":");
    json_string(&report,str_from(differential?"differential":"reference"));
    const char *status=ok?"success":"failure";
    if (result.status==REF_UNAVAILABLE) status="unavailable";
    if (result.status==REF_TIMEOUT || (launch_attempted && run.status==PROCESS_TIMEOUT)) status="timeout";
    if (result.status==REF_CANCELLED || (launch_attempted && run.status==PROCESS_CANCELLED)) status="cancelled";
    if (native_attempted && (built.compile.status==PROCESS_TIMEOUT ||
        (built.identity_attempted && built.compiler_identity.status==PROCESS_TIMEOUT))) status="timeout";
    if (native_attempted && (built.compile.status==PROCESS_CANCELLED ||
        (built.identity_attempted && built.compiler_identity.status==PROCESS_CANCELLED))) status="cancelled";
    if (native_attempted && built.evidence_attempted && built.compiler_evidence.status==PROCESS_TIMEOUT) status="timeout";
    if (native_attempted && built.evidence_attempted && built.compiler_evidence.status==PROCESS_CANCELLED) status="cancelled";
    sb_cstr(&report,",\"status\":"); json_string(&report,str_from(status));
    sb_cstr(&report,",\"operation_id\":"); json_string(&report,str_from(job));
    sb_cstr(&report,",\"requested_lowering\":"); json_string(&report,str_from(native.requested_lowering?native.requested_lowering:"auto"));
    sb_cstr(&report,",\"selected_lowering\":"); json_string(&report,str_from(use_ir?"ir":"ast"));
    sb_fmt(&report,",\"reference_attempted\":%s,\"ir_test_profile\":",reference_attempted?"true":"false");
    if (use_ir) {
        sb_fmt(&report,"{\"status\":\"experimental\",\"schema_version\":%u,\"admitted\":",IR_SCHEMA_VERSION);
        sb_cstr(&report,ir_admitted?"true":"false");
        sb_cstr(&report,",\"source_manifest_sha256\":");
        if (ir_source_hash.len) json_string(&report,ir_source_hash); else sb_cstr(&report,"null");
        sb_cstr(&report,",\"generated_c_sha256\":");
        if (ir_c_hash.len) json_string(&report,ir_c_hash); else sb_cstr(&report,"null");
        sb_cstr(&report,",\"execution_domain\":\"finite binary32, bool, i32, plain records and fixed arrays; let/inout/set and whole-root sink; bounded initialization and loop-state admission\","
            "\"native_budgets\":{\"steps\":1000000,\"call_depth\":128,\"declared_storage_estimate_per_function\":65536},"
            "\"observation_coverage\":\"ordered test/assert/print/f32-bit events, stdout and certified first source trap; no root snapshots\","
            "\"resource_equivalence\":\"not_claimed; interpreter byte and step accounting differs from generated test code\","
            "\"production_backend\":false,\"performance\":\"not_measured\"}");
    } else sb_cstr(&report,"null");
    sb_cstr(&report,",\"stage\":");
    json_string(&report,str_from(compared?"comparison":launch_attempted?"native_execution":native_attempted?"native_compile":
        !reference_attempted || result.status==REF_UNAVAILABLE?"admission":"reference_execution"));
    sb_cstr(&report,",\"reference_status\":"); json_string(&report,str_from(reference_status_name(result.status)));
    if (expected) {
        sb_cstr(&report,",\"verification\":\"expected_source_trap\",\"program_outcome\":");
        json_string(&report,str_from(reference_status_name(result.status)));
        sb_cstr(&report,",\"expected_source_trap\":{\"kind\":");
        json_string(&report,str_from(reference_trap_kind_name(opts.expected_trap.kind)));
        sb_fmt(&report,",\"file\":%u,\"offset\":%u},\"observed_source_trap\":",opts.expected_trap.file,opts.expected_trap.offset);
        if (result.trap_kind!=REF_SOURCE_TRAP_NONE) {
            sb_cstr(&report,"{\"kind\":"); json_string(&report,str_from(reference_trap_kind_name(result.trap_kind)));
            sb_fmt(&report,",\"file\":%u,\"offset\":%u,\"trace_complete\":%s}",result.trap_span.file,result.trap_span.offset,
                result.trap_trace_complete?"true":"false");
        } else sb_cstr(&report,"null");
        sb_fmt(&report,",\"native_source_trap_verified\":%s,\"observation_coverage\":",native_trap_verified?"true":"false");
        json_string(&report,str_from(opts.watch_root.enabled ?
            "ordered_test_assert_print_events_stdout_and_registered_i32_array" : "ordered_test_assert_print_events_and_stdout"));
        sb_cstr(&report,",\"watched_root\":");
        if (opts.watch_root.enabled) sb_fmt(&report,"{\"file\":%u,\"offset\":%u,\"element_type\":\"i32\",\"maximum_elements\":4096}",
            opts.watch_root.file,opts.watch_root.offset);
        else sb_cstr(&report,"null");
    }
    sb_cstr(&report,",\"source_fingerprint\":"); json_string(&report,source_hash);
    sb_cstr(&report,",\"compiler_fingerprint\":"); json_string(&report,compiler);
    sb_cstr(&report,",\"binding_fingerprint\":null,\"artifact_fingerprint\":");
    if (built.executable_fingerprint.len) json_string(&report,built.executable_fingerprint); else sb_cstr(&report,"null");
    sb_cstr(&report,",\"sources\":"); sb_str(&report,sources);
    sb_fmt(&report,",\"tests\":%u,\"failed_tests\":%u,\"assertions\":%llu,\"steps\":%llu,\"allocated_bytes\":%llu,\"compared\":%s",
        result.tests,result.failed_tests,(unsigned long long)result.assertions,(unsigned long long)result.steps,
        (unsigned long long)result.bytes,compared?"true":"false");
    sb_fmt(&report,",\"budgets\":{\"steps\":%llu,\"bytes\":%llu,\"call_depth\":%u,\"timeout_ms\":%u}",
        (unsigned long long)(opts.max_steps?opts.max_steps:1000000),
        (unsigned long long)(opts.max_bytes?opts.max_bytes:64*1024*1024),
        opts.max_call_depth?opts.max_call_depth:128,native.timeout_ms);
    sb_cstr(&report,",\"reference_output_sha256\":"); json_string(&report,hash256_str(a,output));
    sb_cstr(&report,",\"reference_events_sha256\":"); json_string(&report,hash256_str(a,reference_events));
    sb_cstr(&report,",\"native_job\":"); if (built.job_dir) json_string(&report,str_from(built.job_dir)); else sb_cstr(&report,"null");
    sb_cstr(&report,",\"native_executable_sha256\":");
    if (built.executable_fingerprint.len) json_string(&report,built.executable_fingerprint); else sb_cstr(&report,"null");
    sb_cstr(&report,",\"native_status\":");
    if (launch_attempted) json_string(&report,str_from(process_status_name(run.status))); else sb_cstr(&report,"null");
    sb_cstr(&report,",\"native_exit_code\":");
    if (launch_attempted && run.status==PROCESS_EXITED) sb_fmt(&report,"%u",run.exit_code); else sb_cstr(&report,"null");
    sb_cstr(&report,",\"diagnostics\":"); sb_str(&report,diag_render_json(a,d)); sb_cstr(&report,"}\n");
    if (!fs_write(fs_join(a,job,"result.json"),sb_finish(&report))) {
        diag_error(d,1004,SPAN_NONE,"cannot write reference job evidence"); ok=false;
    }
    fprintf(stderr,"beryl: test evidence retained in %s\n",job);
    return ok?0:(use_ir && result.status==REF_UNAVAILABLE?3:1);
}
