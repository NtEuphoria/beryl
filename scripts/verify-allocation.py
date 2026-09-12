"""Verify checked allocator boundaries and injected failure before publication.

Uses a supplied Beryl compiler and Clang, copies a bounded set of source/runtime
inputs, and retains exact generated C, commands, logs, and hashes. It never
installs a compiler, alters a security setting, or retries a denied process.
"""
import argparse, hashlib, json, os, re, shutil, subprocess, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--beryl', required=True, help='candidate Beryl compiler executable')
parser.add_argument('--clang', required=True, help='Clang executable or command')
parser.add_argument('--source-root', type=Path, default=ROOT, help='compiler source/test root to verify')
parser.add_argument('--runtime-dir', type=Path, help='runtime source directory; defaults to source-root/runtime')
parser.add_argument('--output-root', type=Path, default=ROOT/'build', help='parent for a new isolated result directory')
args = parser.parse_args()
def executable(name):
    found = shutil.which(name)
    if not found: raise RuntimeError(f'Executable unavailable: {name}')
    return Path(found).resolve()
CLANG = executable(args.clang)
COMPILER_INPUT = executable(args.beryl)
SOURCE = args.source_root.resolve()
RUNTIME = (args.runtime_dir or SOURCE/'runtime').resolve()
args.output_root.mkdir(parents=True, exist_ok=True)
OUT = Path(tempfile.mkdtemp(prefix='allocation-', dir=args.output_root.resolve()))
SNAP = OUT/'inputs'
PATHS = ['src/common/arena.c','src/common/arena.h','src/common/vec.c','src/common/vec.h',
         'src/common/str.c','src/common/map.c',
         'src/common/str.h','src/common/map.h','src/common/checked_size.h',
         'tests/unit/test_allocation.c','tests/unit/test_common.c','tests/unit/test.c','tests/unit/test.h']
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
files = {p:SOURCE/p for p in PATHS}
files.update({'runtime/'+name:RUNTIME/name for name in ('beryl_rt.c','beryl_rt.h')})
files['beryl'+COMPILER_INPUT.suffix] = COMPILER_INPUT
record = {'schema_version':1,'status':'running','operation':'allocation_verification',
          'scope':'supplied compiler plus captured allocator/runtime sources; caller establishes compiler/source provenance',
          'source_root':str(SOURCE),'runtime_dir':str(RUNTIME),'compiler_input':str(COMPILER_INPUT),
          'commands':[]}
REPORT = OUT/'results.json'
env = os.environ.copy(); env['PATH'] = str(CLANG.parent)+os.pathsep+env.get('PATH','')
def run(args, *, expect=0, cwd=SNAP):
    args = list(map(str,args)); started=time.monotonic()
    try:
        p = subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,
                           encoding='utf-8',errors='replace',timeout=90)
    except (OSError, subprocess.TimeoutExpired) as exc:
        record['commands'].append({'argv':args,'failure':type(exc).__name__,'detail':str(exc)})
        raise
    record['commands'].append({'argv':args,'exit':p.returncode,'seconds':time.monotonic()-started,
                               'stdout':p.stdout,'stderr':p.stderr})
    if expect is not None and p.returncode!=expect: raise RuntimeError(f'Exit {p.returncode}: {args}\n{p.stdout}\n{p.stderr}')
    return p
print(OUT,flush=True)
try:
    before = {p:digest(src) for p,src in files.items()}
    for p,src in files.items():
        (SNAP/p).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src,SNAP/p)
        if digest(SNAP/p)!=before[p]: raise RuntimeError('Input changed while copying: '+p)
    if before != {p:digest(src) for p,src in files.items()}: raise RuntimeError('Input changed while copying')
    record['source_hashes']=before
    record['script_sha256']=digest(Path(__file__))
    record['toolchain']=run([CLANG,'--version']).stdout
    common=['-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Isrc']
    (SNAP/'allocation_main.c').write_text('#include "tests/unit/test.h"\nvoid run_common_tests(void);\nvoid run_allocation_tests(void);\nint main(void){run_common_tests();run_allocation_tests();return t_summary();}\n')
    unit_src=['src/common/arena.c','src/common/vec.c','src/common/str.c','src/common/map.c',
              'tests/unit/test.c','tests/unit/test_common.c','tests/unit/test_allocation.c','allocation_main.c']
    record['unit']={}
    for opt in ['-O0','-O2']:
        binary=OUT/('unit'+opt+('.exe' if os.name=='nt' else ''))
        run([CLANG,*common,opt,'-fsanitize=undefined','-fno-sanitize-recover=all',*unit_src,'-o',binary])
        record['unit'][opt]=run([binary]).stdout.strip()
    compiler=SNAP/('beryl'+COMPILER_INPUT.suffix)
    fixture=SNAP/'list.be'
    fixture.write_text('module p1\nfn main() { var values: List<i32>\n for i in 0..100 { values.push(i) }\n println(values.get(99))\n}\n')
    generated=run([compiler,'emit-c',fixture]).stdout
    if 'be_list_growth_plan' not in generated or 'beryl_allocation_size_failure' not in generated:
        raise RuntimeError('Supplied compiler did not emit checked native List growth')
    (SNAP/'list.c').write_text(generated)
    match=re.search(r'typedef struct \{ int32_t \*data; int32_t len; int32_t cap; \} (\w+);',generated)
    if not match: raise RuntimeError('No generated i32 List type')
    typ=match[1]
    probe=r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
static int failure;
static void check_before_failure(void);
static void *p1_malloc(size_t n) {
    if (failure==1) { check_before_failure(); return NULL; }
    if (failure==3 || failure==4) { fputs("unexpected allocation\n",stderr); exit(91); }
    return malloc(n);
}
static void *p1_calloc(size_t n,size_t e) {
    if (failure==2) return NULL;
    if (failure==3) { fputs("unexpected allocation\n",stderr); exit(91); }
    return calloc(n,e);
}
#define malloc p1_malloc
#define calloc p1_calloc
#include "src/common/arena.c"
#undef malloc
#undef calloc
#include "src/common/vec.c"
#include "src/common/str.c"
#include "src/common/map.c"
#define main emitted_main
#include "list.c"
#undef main
static LIST watched_list;
static VEC(int32_t) watched_vector;
static SB watched_sb;
static void *prior_data;
static int watch;
static void check_before_failure(void) {
    if (watch==1) {
        if (watched_list.data!=prior_data || watched_list.len!=8 || watched_list.cap!=8 || watched_list.data[0]!=17) exit(92);
        puts("list descriptor and prefix preserved"); fflush(stdout);
    } else if (watch==2) {
        if (watched_vector.data!=prior_data || watched_vector.len!=8 || watched_vector.cap!=8 || watched_vector.data[0]!=17) exit(92);
        puts("vector descriptor and prefix preserved"); fflush(stdout);
    } else if (watch==3) {
        if (watched_sb.buf!=prior_data || watched_sb.len!=8 || watched_sb.cap!=8 || watched_sb.buf[0]!='x') exit(92);
        puts("string descriptor and prefix preserved"); fflush(stdout);
    }
}
static void *p1_realloc(void *p,size_t n) {
    if (failure==1) { check_before_failure(); return NULL; }
    if (failure==3) { fputs("unexpected allocation\n",stderr); exit(91); }
    return realloc(p,n);
}
#define realloc p1_realloc
#include "runtime/beryl_rt.c"
#undef realloc
int main(int argc,char **argv) {
    if (argc!=2) return 93;
    const char *mode=argv[1];
    if (!strcmp(mode,"arena-header-overflow")) { failure=4; arena_new(SIZE_MAX); }
    if (!strcmp(mode,"arena-calloc-failure")) { failure=2; arena_new(37); }
    if (!strcmp(mode,"arena-malloc-failure")) { failure=1; arena_new(37); }
    Arena *a=arena_new(37);
    if (!strcmp(mode,"arena-array-overflow")) { failure=3; ARENA_ARRAY(a,uint64_t,SIZE_MAX/8+1); }
    if (!strcmp(mode,"arena-used-overflow")) { a->total_used=SIZE_MAX; failure=3; arena_alloc(a,1,1); }
    if (!strcmp(mode,"arena-reserved-overflow")) { a->total_reserved=SIZE_MAX; failure=3; arena_alloc(a,128,1); }
    if (!strcmp(mode,"arena-alignment-overflow")) { failure=3; arena_alloc(a,SIZE_MAX,16); }
    if (!strcmp(mode,"arena-invalid-alignment")) { failure=3; arena_alloc(a,1,3); }
    if (!strcmp(mode,"vector-length-overflow")) {
        VEC(int32_t) v={.data=(int32_t *)(uintptr_t)1,.len=UINT32_MAX,.cap=UINT32_MAX}; failure=3; vec_push(a,v,1);
    }
    if (!strcmp(mode,"vector-invalid-length")) {
        VEC(int32_t) v={.data=(int32_t *)(uintptr_t)1,.len=2,.cap=1}; failure=3; vec_push(a,v,1);
    }
    if (!strcmp(mode,"vector-byte-overflow")) { void *p=NULL; uint32_t cap=0; failure=3; vec_reserve_(a,&p,&cap,2,0,SIZE_MAX); }
    if (!strcmp(mode,"vector-wide-need")) { void *p=NULL; uint32_t cap=0; failure=3; vec_reserve_(a,&p,&cap,SIZE_MAX,0,2); }
    if (!strcmp(mode,"vector-malloc-failure")) {
        for (int32_t i=0;i<8;i++) vec_push(a,watched_vector,i+17);
        prior_data=watched_vector.data; watch=2; failure=1; vec_reserve(a,watched_vector,1000);
    }
    if (!strcmp(mode,"string-length-overflow")) {
        SB sb={.a=a,.buf=(char *)(uintptr_t)1,.len=UINT32_MAX,.cap=UINT32_MAX}; failure=3; sb_char(&sb,'x');
    }
    if (!strcmp(mode,"string-format-terminator-overflow")) {
        SB sb={.a=a,.buf=(char *)(uintptr_t)1,.len=UINT32_MAX-1,.cap=UINT32_MAX}; failure=3; sb_fmt(&sb,"%s","x");
    }
    if (!strcmp(mode,"string-malloc-failure")) {
        watched_sb=(SB){.a=a,.buf=arena_alloc(a,8,1),.len=8,.cap=8}; watched_sb.buf[0]='x';
        prior_data=watched_sb.buf; watch=3; failure=1; sb_reserve(&watched_sb,1000);
    }
    if (!strcmp(mode,"map-capacity-overflow")) {
        Map m={.a=a,.slots=(Slot *)(uintptr_t)1,.cap=UINT32_C(1)<<31,.len=UINT32_C(1503238554)};
        failure=3; map_put(&m,STR_LIT("x"),NULL);
    }
    if (!strcmp(mode,"interner-capacity-overflow")) {
        Interner in={.a=a,.slots=(ISlot *)(uintptr_t)1,.cap=UINT32_C(1)<<31,.len=UINT32_C(1503238554)};
        failure=3; intern(&in,STR_LIT("x"));
    }
    if (!strcmp(mode,"list-capacity-overflow")) {
        watched_list=(LIST){.data=(int32_t *)(uintptr_t)1,.len=INT32_MAX,.cap=INT32_MAX};
        beryl_test_trace_enable(); beryl_test_trap_site(0,7); failure=3; LIST_push(&watched_list,1);
    }
    if (!strcmp(mode,"list-realloc-failure")) {
        watched_list=(LIST){.data=malloc(8*sizeof(int32_t)),.len=8,.cap=8};
        watched_list.data[0]=17; prior_data=watched_list.data; watch=1; failure=1;
        beryl_test_trace_enable(); beryl_test_trap_site(0,7); LIST_push(&watched_list,1);
    }
    if (!strcmp(mode,"list-success")) {
        for (int32_t i=0;i<10000;i++) LIST_push(&watched_list,i);
        if (watched_list.len!=10000 || watched_list.cap<10000) return 94;
        for (int32_t i=0;i<10000;i++) if (watched_list.data[i]!=i) return 95;
        beryl_release(watched_list.data); arena_free(a); return 0;
    }
    return 96;
}
'''.replace('LIST',typ)
    (SNAP/'probe.c').write_text(probe)
    cases={
      'arena-header-overflow':'allocation size overflow',
      'arena-array-overflow':'allocation size overflow',
      'arena-used-overflow':'allocation size overflow',
      'arena-reserved-overflow':'allocation size overflow',
      'arena-alignment-overflow':'allocation size overflow',
      'arena-invalid-alignment':'invalid compiler arena alignment',
      'arena-calloc-failure':'out of memory allocating',
      'arena-malloc-failure':'out of memory allocating',
      'vector-length-overflow':'compiler vector capacity',
      'vector-invalid-length':'compiler vector capacity',
      'vector-byte-overflow':'compiler vector capacity',
      'vector-wide-need':'compiler vector capacity',
      'vector-malloc-failure':'out of memory allocating',
      'string-length-overflow':'compiler string or interner capacity limit exceeded',
      'string-format-terminator-overflow':'compiler string or interner capacity limit exceeded',
      'string-malloc-failure':'out of memory allocating',
      'map-capacity-overflow':'compiler map capacity limit exceeded',
      'interner-capacity-overflow':'compiler string or interner capacity limit exceeded',
      'list-capacity-overflow':'list allocation size or capacity limit exceeded',
      'list-realloc-failure':'out of memory growing a list',
    }
    record['probes']={}
    for opt in ['-O0','-O2']:
        binary=OUT/('probe'+opt+('.exe' if os.name=='nt' else ''))
        run([CLANG,*common,'-Wno-unused-function','-Wno-unused-variable','-Iruntime',opt,
             '-fsanitize=undefined','-fno-sanitize-recover=all','probe.c','-o',binary])
        run([binary,'list-success'])
        passed=[]
        for case,message in cases.items():
            p=run([binary,case],expect=None)
            if p.returncode in (0,91,92,93,94,95,96) or message not in p.stderr:
                raise RuntimeError(f'Wrong failure for {case}: {p.returncode} {p.stdout} {p.stderr}')
            if 'runtime error:' in p.stderr or '"event":"source_trap"' in p.stderr:
                raise RuntimeError(f'Misclassified failure for {case}: {p.stderr}')
            if case.endswith('realloc-failure') and 'list descriptor and prefix preserved' not in p.stdout:
                raise RuntimeError('List descriptor changed before allocator returned')
            if case=='vector-malloc-failure' and 'vector descriptor and prefix preserved' not in p.stdout:
                raise RuntimeError('Vector descriptor changed before allocator returned')
            if case=='string-malloc-failure' and 'string descriptor and prefix preserved' not in p.stdout:
                raise RuntimeError('String descriptor changed before allocator returned')
            passed.append(case)
        record['probes'][opt]=passed
    record['generated_list_sha256']=digest(SNAP/'list.c')
    record['compiler_sha256']=digest(compiler)
    record['status']='passed'
except BaseException as exc:
    record['status']='cancelled' if isinstance(exc,KeyboardInterrupt) else 'failed'
    record['failure']={'type':type(exc).__name__,'detail':str(exc)}
    raise
finally:
    REPORT.write_text(json.dumps(record,indent=2))
    print(REPORT,flush=True)
