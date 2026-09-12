#include "test.h"
#include "../../src/parse/parser.h"
#include "../../src/sema/check.h"
#include "../../src/sema/storage.h"

static void storage_case(const char *name,const char *source,bool native_ok,bool enfusion_ok) {
    CASE(name);
    for (uint32_t target=STORAGE_NATIVE;target<=STORAGE_ENFUSION;target++) {
        Arena *a=arena_new(0); SourceMap *sm=srcmap_new(a); DiagBag *d=diag_new(a,sm);
        Interner *in=intern_new(a); Program *p=prog_new(a); SB code; sb_init(&code,a);
        sb_cstr(&code,"module storage\n"); sb_cstr(&code,source);
        uint32_t file=srcmap_add(sm,STR_LIT("storage.be"),sb_finish(&code));
        TokenVec tokens=lex_file(a,sm,d,in,file); prog_add_module(p,parse_file(a,d,in,tokens,file));
        bool typed=!diag_errors(d) && resolve_program(d,p) && check_program(d,p);
        CHECK(typed);
        bool expected=target==STORAGE_NATIVE?native_ok:enfusion_ok;
        if (typed) {
            bool result=storage_admit(d,p,(StorageTarget)target); CHECK_EQ_I(result,expected);
            if (!expected) { CHECK_CONTAINS(diag_render_str(a,d),target==STORAGE_NATIVE?"BE0903":"BE0701"); CHECK_CONTAINS(diag_render_str(a,d),"storage admission"); }
        }
        if (diag_errors(d) && (!typed || expected)) { Str text=diag_render_str(a,d); printf("%.*s\n",(int)text.len,text.ptr); }
        arena_free(a);
    }
}

void run_storage_admission_tests(void) {
    storage_case("storage: scalar/plain records preserve copies and returns",
        "struct R{x:i32}\nfn clone(r:R)->R {var b=r\nb.x=4\nreturn b}\n"
        "fn main(){var r=R{x:1}\nlet b=clone(r)\nprintln(b.x)}\n",true,true);
    storage_case("storage: scalar fixed-array value copy differs by target",
        "fn main(){var a=[1,2]\nvar b=a\nb[0]=9\nprintln(a[0])}\n",true,false);
    storage_case("storage: scalar List construction and borrow preserved",
        "fn size(let xs:List<i32>)->i32{return xs.len()}\n"
        "fn add(inout xs:List<i32>){xs.push(7)}\n"
        "fn main(){var xs:List<i32>\nadd(inout xs)\nprintln(size(xs))}\n",true,true);
    storage_case("storage: owning List descriptor binding rejected",
        "fn main(){var a:List<i32>\na.push(1)\nvar b=a\nb.push(2)}\n",false,false);
    storage_case("storage: owning List replacement rejected",
        "fn main(){var a:List<i32>\nvar b:List<i32>\na=b}\n",false,false);
    storage_case("storage: scalar List field copies only through Enfusion helper",
        "struct S{xs:List<i32>}\nfn main(){var a=S{}\na.xs.push(1)\nvar b=a\nb.xs.push(2)}\n",false,true);
    storage_case("storage: nested owning record copies classified recursively",
        "struct S{xs:List<i32>}\nstruct W{s:S}\nfn main(){var a=W{s:S{}}\nvar b=a}\n",false,true);
    storage_case("storage: native owning replacement rejects even fresh literal",
        "struct S{xs:List<i32>}\nfn main(){var a=S{}\na.xs.push(1)\na=S{}}\n",false,true);
    storage_case("storage: nested owning array copy rejected",
        "struct S{xs:List<i32>}\nfn main(){var a=[S{}]\nvar b=a}\n",false,false);
    storage_case("storage: List literal embedding cannot create shallow alias",
        "struct S{xs:List<i32>}\nfn main(){var xs:List<i32>\nvar s=S{xs:xs}}\n",false,false);
    storage_case("storage: owning return signature rejected",
        "fn make()->List<i32>{var xs:List<i32>\nxs.push(1)\nreturn xs}\n",false,false);
    storage_case("storage: record owning return signature rejected",
        "struct S{xs:List<i32>}\nfn make()->S{return S{}}\n",false,false);
    storage_case("storage: owning sink transfer rejected",
        "fn consume(sink xs:List<i32>){println(xs.len())}\nfn main(){var xs:List<i32>\nconsume(sink xs)}\n",false,false);
    storage_case("storage: owning set transfer rejected",
        "struct S{xs:List<i32>}\nfn init(set s:S){s=S{}}\n",false,false);
    storage_case("storage: read-only scalar List iteration preserved",
        "fn main(){var xs:List<i32>\nxs.push(3)\nvar sum=0\nfor v in xs{sum+=v}\nprintln(sum)}\n",true,true);
    storage_case("storage: mutation during List iteration rejected",
        "fn main(){var xs:List<i32>\nxs.push(1)\nfor v in xs{xs.push(v)}}\n",false,false);
    storage_case("storage: callee mutation during List iteration rejected",
        "fn clear(inout xs:List<i32>){xs.clear()}\nfn main(){var xs:List<i32>\nfor v in xs{clear(inout xs)}}\n",false,false);
    storage_case("storage: scalar array iteration snapshot versus engine borrow",
        "fn main(){var xs=[1,2]\nfor v in xs{xs[0]=v}}\n",true,false);
    storage_case("storage: nested call cannot invalidate captured argument",
        "fn mutate(inout xs:List<i32>)->i32{xs.push(7)\nreturn 0}\n"
        "fn read(let xs:List<i32>,v:i32)->i32{return xs.len()+v}\n"
        "fn main(){var xs:List<i32>\nprintln(read(xs,mutate(inout xs)))}\n",false,false);
    storage_case("storage: captured method receiver cannot be invalidated",
        "struct S{xs:List<i32>}\nfn S.read(let self,v:i32)->i32{return self.xs.len()+v}\n"
        "fn mutate(inout s:S)->i32{s.xs.push(7)\nreturn 0}\n"
        "fn main(){var s=S{}\nprintln(s.read(mutate(inout s)))}\n",false,false);
    storage_case("storage: storage-derived scalar argument capture protected",
        "fn mutate(inout xs:List<i32>)->i32{xs.push(7)\nreturn 0}\n"
        "fn read(inout v:i32,n:i32){v+=n}\n"
        "fn main(){var xs:List<i32>\nxs.push(1)\nread(inout xs[0],mutate(inout xs))}\n",false,false);
    storage_case("storage: nonmutating nested arguments allowed",
        "fn read(let xs:List<i32>,v:i32)->i32{return xs.len()+v}\n"
        "fn count(let xs:List<i32>)->i32{return xs.len()}\n"
        "fn main(){var xs:List<i32>\nprintln(read(xs,count(xs)))}\n",true,true);
    storage_case("storage: scalar let field capture does not retain receiver storage",
        "struct Counter{value:i32}\nfn Counter.next(inout self)->i32{self.value+=1\nreturn self.value}\n"
        "fn main(){var c=Counter{value:1}\nprintln(min(c.value,c.next()))}\n",true,true);
    storage_case("storage: scalar let index capture does not retain collection storage",
        "fn grow(inout xs:List<i32>)->i32{xs.push(9)\nreturn 0}\n"
        "fn read(value:i32,n:i32)->i32{return value+n}\n"
        "fn main(){var xs:List<i32>\nxs.push(1)\nprintln(read(xs[0],grow(inout xs)))}\n",true,true);
    storage_case("storage: collection index evaluation cannot invalidate base",
        "fn grow(inout xs:List<i32>)->i32{xs.push(9)\nreturn 0}\n"
        "fn main(){var xs:List<i32>\nfor i in 0..8{xs.push(i)}\nprintln(xs[grow(inout xs)])}\n",false,false);
    storage_case("storage: separated index evaluation preserves supported access",
        "fn grow(inout xs:List<i32>)->i32{xs.push(9)\nreturn 0}\n"
        "fn main(){var xs:List<i32>\nfor i in 0..8{xs.push(i)}\nlet i=grow(inout xs)\nprintln(xs[i])}\n",true,true);
    storage_case("storage: owning copy in dead source rejected",
        "fn main(){return\nvar xs:List<i32>\nvar ys=xs}\n",false,false);
    storage_case("storage: array insertion of reference-valued place rejected",
        "struct R{x:i32}\nfn main(){var r=R{x:1}\nvar a=[r]}\n",true,false);
    storage_case("storage: fresh scalar record array construction allowed",
        "struct R{x:i32}\nfn main(){var a=[R{x:1}]}\n",true,true);
    storage_case("storage: List plain records target-specific element copy",
        "struct R{x:i32}\nfn main(){var xs:List<R>\nxs.push(R{x:1})\nvar r=xs.get(0)}\n",true,false);
    storage_case("storage: nested reference collection helper rejected",
        "struct S{xs:List<List<i32>>}\n",true,false);
    storage_case("storage: read-only fixed-array argument remains borrowed",
        "fn first(let a:[i32;2])->i32{return a[0]}\nfn main(){var a=[1,2]\nprintln(first(a))}\n",true,true);
    storage_case("storage: scalar array field record copy retains helper support",
        "struct S{xs:[i32;2]}\nfn main(){var a=S{xs:[1,2]}\nvar b=a}\n",true,true);
    storage_case("storage: unknown wrapper borrow is not claimed as supported",
        "fn inspect(let x:Box<i32>){ }\n",false,false);
    storage_case("storage: shared-reference parameter needs a retention contract",
        "fn inspect(let x:Rc<i32>){ }\n",false,false);

    CASE("storage: recursive classification is bounded and does not call cycles plain");
    Type scalar_type={.kind=TY_INT,.bits=32,.is_signed=true};
    Type list={.kind=TY_LIST,.elem=&scalar_type},array={.kind=TY_ARRAY,.elem=&list,.array_len=2};
    StorageClass c=storage_classify(&array,STORAGE_NATIVE);
    CHECK(c.flags&STORAGE_OWNED); CHECK(!c.logical_copy_supported);
    Type cyclic={.kind=TY_ARRAY,.array_len=1}; cyclic.elem=&cyclic;
    c=storage_classify(&cyclic,STORAGE_NATIVE); CHECK(c.flags&STORAGE_UNKNOWN); CHECK(!c.logical_copy_supported);
    c=storage_classify(&scalar_type,(StorageTarget)-1); CHECK(c.flags&STORAGE_UNKNOWN);
    Type shared={.kind=TY_RC,.elem=&scalar_type}; c=storage_classify(&shared,STORAGE_ENFUSION);
    CHECK(c.flags&STORAGE_SHARED); CHECK(!c.logical_copy_supported);
}
