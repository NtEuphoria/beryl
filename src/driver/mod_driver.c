#include "mod_driver.h"
#include "process.h"
#include "../common/fs.h"
#include "../common/json.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

int driver_mod(int argc,char **argv) {
    if(argc<0 || argc>INT_MAX-7) { fprintf(stderr,"beryl: mod argument count exceeds supported limit\n"); return 2; }
    Arena *a=arena_new(0);
    const char *exe=fs_executable(a);
    const char *python=NULL,*tool=NULL;
    if (!process_environment(a,"BERYL_PYTHON",&python) || !process_environment(a,"BERYL_MOD_TOOL",&tool)) {
        fprintf(stderr,"beryl: cannot read mod-tool configuration as bounded UTF-8 paths\n");
        arena_free(a); return 2;
    }
    if (!python || !*python) python="python";
    if ((!tool || !*tool) && exe) {
        size_t n=strlen(exe);
        while (n && exe[n-1]!='/' && exe[n-1]!='\\') n--;
        const char *dir=str_cstr(a,str_new(exe,(uint32_t)n));
        tool=fs_join(a,dir,"beryl-tools/mod.py");
    }
    Str script;
    if (!exe || !tool || !fs_read(a,tool,&script)) {
        fprintf(stderr,"beryl: installed mod tool unavailable; install beryl-tools beside the compiler or set BERYL_MOD_TOOL to the trusted installed mod.py\n");
        arena_free(a); return 2;
    }
    const char *job=fs_job_dir(a,".beryl-cache");
    if (!job) { fprintf(stderr,"beryl: cannot create mod dispatch job\n"); arena_free(a); return 2; }
    const char **args=ARENA_ARRAY(a,const char *,argc+7);
    args[0]=python; args[1]="-I"; args[2]=fs_absolute(a,tool);
    args[3]="--beryl"; args[4]=exe;
    for (int i=0;i<argc;i++) args[i+5]=argv[i];
    args[argc+5]=NULL;
    ProcessResult result=process_run(a,(ProcessOpts){.argv=args,.log_dir=job,.log_name="mod",.timeout_ms=1800000});
    bool output_ok=fwrite(result.out.ptr,1,result.out.len,stdout)==result.out.len && !fflush(stdout);
    output_ok=fwrite(result.err.ptr,1,result.err.len,stderr)==result.err.len && !fflush(stderr) && output_ok;
    SB report; sb_init(&report,a);
    sb_cstr(&report,"{\"schema_version\":1,\"operation\":\"mod_dispatch\",\"stage\":\"tool_process\",\"status\":");
    json_string(&report,str_from(output_ok?process_status_name(result.status):"io_failure"));
    sb_cstr(&report,",\"exit_code\":");
    if (result.status==PROCESS_EXITED) sb_fmt(&report,"%u",result.exit_code); else sb_cstr(&report,"null");
    sb_cstr(&report,",\"stdout\":"); json_string(&report,str_from(result.stdout_path?result.stdout_path:""));
    sb_cstr(&report,",\"stderr\":"); json_string(&report,str_from(result.stderr_path?result.stderr_path:""));
    sb_char(&report,'}');
    bool saved=fs_write(fs_join(a,job,"result.json"),sb_finish(&report));
    int code=output_ok&&saved&&result.status==PROCESS_EXITED ? (int)(result.exit_code>255?1:result.exit_code) : 2;
    if (result.status!=PROCESS_EXITED) fprintf(stderr,"beryl: mod tool %s; evidence: %s\n",process_status_name(result.status),job);
    arena_free(a); return code;
}
