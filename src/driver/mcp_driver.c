#include "mcp_driver.h"
#include "process.h"
#include "../common/fs.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

int driver_mcp(int argc, char **argv) {
    if (argc<0 || argc>INT_MAX-6) {
        fprintf(stderr,"beryl: MCP argument count exceeds supported limit\n"); return 2;
    }
    Arena *a=arena_new(0);
    const char *exe=fs_executable(a), *python=NULL, *tool=NULL;
    if (!process_environment(a,"BERYL_PYTHON",&python) || !process_environment(a,"BERYL_MCP_TOOL",&tool)) {
        fprintf(stderr,"beryl: MCP path environment value is invalid or exceeds its supported limit\n");
        arena_free(a); return 2;
    }
    if (!python || !*python) python="python";
    python=process_find_executable(a,python);
    if ((!tool || !*tool) && exe) {
        size_t n=strlen(exe);
        while (n && exe[n-1]!='/' && exe[n-1]!='\\') n--;
        tool=fs_join(a,str_cstr(a,str_new(exe,(uint32_t)n)),"beryl-tools/mcp.py");
    }
    tool=tool?fs_absolute(a,tool):NULL;
    FILE *script=tool?fs_open(tool,"rb"):NULL;
    if (!exe || !python || !script) {
        if (script) fclose(script);
        fprintf(stderr,"beryl: installed MCP tool or Python unavailable; install beryl-tools beside the compiler or configure trusted BERYL_MCP_TOOL and BERYL_PYTHON paths\n");
        arena_free(a); return 2;
    }
    if (fclose(script)!=0 || fflush(stdout)!=0 || fflush(stderr)!=0) {
        fprintf(stderr,"beryl: MCP stream setup failed\n"); arena_free(a); return 2;
    }
    const char **args=ARENA_ARRAY(a,const char *,argc+6);
    args[0]=python; args[1]="-I"; args[2]=tool; args[3]="--beryl"; args[4]=exe;
    for (int i=0;i<argc;i++) args[i+5]=argv[i];
    args[argc+5]=NULL;
    ProcessResult result=process_run(a,(ProcessOpts){.argv=args,.inherit_stdio=true});
    int code=result.status==PROCESS_EXITED?(int)(result.exit_code>255?1:result.exit_code):2;
    if (result.status!=PROCESS_EXITED)
        fprintf(stderr,"beryl: MCP tool %s (OS error %u)\n",process_status_name(result.status),result.os_error);
    arena_free(a); return code;
}
