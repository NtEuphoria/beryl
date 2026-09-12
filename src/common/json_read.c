#include "json_read.h"
#include <string.h>

typedef struct {
    Arena *arena;
    Str input;
    JsonLimits limits;
    JsonReadError *error;
    uint32_t at, nodes, strings, work;
} Reader;

JsonLimits json_read_limits(void) {
    return (JsonLimits){1048576, 16384, 48, 1048576, 8388608};
}
static bool fail(Reader *r, const char *message, bool limit) {
    if (!r->error->message) *r->error = (JsonReadError){message,r->at,limit};
    return false;
}
static bool charge(Reader *r, uint32_t n) {
    if (n > r->limits.work - r->work) return fail(r,"JSON work limit exceeded",true);
    r->work += n; return true;
}
static bool take(Reader *r) { if (!charge(r,1)) return false; r->at++; return true; }
static bool space(Reader *r) {
    while (r->at < r->input.len) {
        char c = r->input.ptr[r->at];
        if (c!=' ' && c!='\t' && c!='\r' && c!='\n') break;
        if (!take(r)) return false;
    }
    return true;
}
/* Returns the width of one well-formed scalar; zero is invalid/truncated. */
static uint32_t scalar(const unsigned char *p, uint32_t n) {
    if (!n) return 0;
    if (p[0] < 0x80) return 1;
    uint32_t w; uint32_t code;
    if (p[0] >= 0xc2 && p[0] <= 0xdf) { w=2; code=p[0]&31; }
    else if (p[0] >= 0xe0 && p[0] <= 0xef) { w=3; code=p[0]&15; }
    else if (p[0] >= 0xf0 && p[0] <= 0xf4) { w=4; code=p[0]&7; }
    else return 0;
    if (w>n) return 0;
    for (uint32_t i=1;i<w;i++) { if ((p[i]&0xc0)!=0x80) return 0; code=(code<<6)|(p[i]&63); }
    if ((w==2 && code<0x80) || (w==3 && code<0x800) || (w==4 && code<0x10000) ||
        code>0x10ffff || (code>=0xd800 && code<=0xdfff)) return 0;
    return w;
}
bool json_utf8(Str s, uint32_t *bad_offset) {
    if (s.len && !s.ptr) { if (bad_offset) *bad_offset=0; return false; }
    for (uint32_t at=0;at<s.len;) {
        uint32_t n=scalar((const unsigned char *)s.ptr+at,s.len-at);
        if (!n) { if (bad_offset) *bad_offset=at; return false; } at+=n;
    }
    return true;
}
static int hex(char c) {
    if(c>='0'&&c<='9')return c-'0'; if(c>='a'&&c<='f')return c-'a'+10;
    if(c>='A'&&c<='F')return c-'A'+10; return -1;
}
static bool code_unit(Reader *r, uint32_t *code) {
    if(r->input.len-r->at<4)return fail(r,"truncated Unicode escape",false);
    uint32_t v=0;
    for(uint32_t i=0;i<4;i++) { int x=hex(r->input.ptr[r->at]);
        if(x<0)return fail(r,"invalid Unicode escape",false);
        v=v*16+(uint32_t)x; if(!take(r))return false; }
    *code=v;return true;
}
static bool append(Reader *r, SB *b, const char *p, uint32_t n) {
    if(n>r->limits.string_bytes-r->strings)return fail(r,"JSON decoded-string limit exceeded",true);
    r->strings+=n; sb_str(b,str_new(p,n));return true;
}
static bool string(Reader *r, Str *out) {
    if(!take(r))return false; SB b;sb_init(&b,r->arena);
    while(r->at<r->input.len) {
        unsigned char c=(unsigned char)r->input.ptr[r->at];
        if(c=='"'){if(!take(r))return false;*out=sb_finish(&b);return true;}
        if(c<0x20)return fail(r,"unescaped control character in string",false);
        if(c!='\\') {
            uint32_t n=scalar((const unsigned char *)r->input.ptr+r->at,r->input.len-r->at);
            if(!n)return fail(r,"invalid UTF-8 in string",false);
            if(!charge(r,n)||!append(r,&b,r->input.ptr+r->at,n))return false;
            r->at+=n;continue;
        }
        if(!take(r))return false;
        if(r->at==r->input.len)return fail(r,"truncated string escape",false);
        c=(unsigned char)r->input.ptr[r->at];if(!take(r))return false;
        char v=0;
        switch(c) {
            case '"':v='"';break;case '\\':v='\\';break;case '/':v='/';break;
            case 'b':v='\b';break;case 'f':v='\f';break;case 'n':v='\n';break;
            case 'r':v='\r';break;case 't':v='\t';break;
            case 'u': {
                uint32_t cp;if(!code_unit(r,&cp))return false;
                if(cp>=0xd800&&cp<=0xdbff) {
                    if(r->input.len-r->at<2||r->input.ptr[r->at]!='\\'||r->input.ptr[r->at+1]!='u')
                        return fail(r,"high surrogate requires low surrogate",false);
                    if(!take(r)||!take(r))return false;
                    uint32_t low;if(!code_unit(r,&low))return false;
                    if(low<0xdc00||low>0xdfff)return fail(r,"invalid low surrogate",false);
                    cp=0x10000+((cp-0xd800)<<10)+(low-0xdc00);
                } else if(cp>=0xdc00&&cp<=0xdfff)return fail(r,"unpaired low surrogate",false);
                char encoded[4];uint32_t n;
                if(cp<0x80){encoded[0]=(char)cp;n=1;}
                else if(cp<0x800){encoded[0]=(char)(0xc0|(cp>>6));encoded[1]=(char)(0x80|(cp&63));n=2;}
                else if(cp<0x10000){encoded[0]=(char)(0xe0|(cp>>12));encoded[1]=(char)(0x80|((cp>>6)&63));encoded[2]=(char)(0x80|(cp&63));n=3;}
                else {encoded[0]=(char)(0xf0|(cp>>18));encoded[1]=(char)(0x80|((cp>>12)&63));encoded[2]=(char)(0x80|((cp>>6)&63));encoded[3]=(char)(0x80|(cp&63));n=4;}
                if(!append(r,&b,encoded,n))return false;continue;
            }
            default:return fail(r,"invalid string escape",false);
        }
        if(!append(r,&b,&v,1))return false;
    }
    return fail(r,"unterminated string",false);
}
static bool digit(char c){return c>='0'&&c<='9';}
static bool number(Reader *r, Str *out) {
    uint32_t start=r->at;
    if(r->input.ptr[r->at]=='-'&&!take(r))return false;
    if(r->at==r->input.len||!digit(r->input.ptr[r->at]))return fail(r,"invalid number",false);
    if(r->input.ptr[r->at]=='0'){if(!take(r))return false;}
    else while(r->at<r->input.len&&digit(r->input.ptr[r->at]))if(!take(r))return false;
    if(r->at<r->input.len&&r->input.ptr[r->at]=='.') {
        if(!take(r))return false;
        if(r->at==r->input.len||!digit(r->input.ptr[r->at]))return fail(r,"missing fractional digits",false);
        while(r->at<r->input.len&&digit(r->input.ptr[r->at]))if(!take(r))return false;
    }
    if(r->at<r->input.len&&(r->input.ptr[r->at]=='e'||r->input.ptr[r->at]=='E')) {
        if(!take(r))return false;
        if(r->at<r->input.len&&(r->input.ptr[r->at]=='+'||r->input.ptr[r->at]=='-'))if(!take(r))return false;
        if(r->at==r->input.len||!digit(r->input.ptr[r->at]))return fail(r,"missing exponent digits",false);
        while(r->at<r->input.len&&digit(r->input.ptr[r->at]))if(!take(r))return false;
    }
    *out=str_slice(r->input,start,r->at-start);return true;
}
static JsonValue *value(Reader *r,uint32_t depth) {
    if(depth>r->limits.depth){fail(r,"JSON depth limit exceeded",true);return NULL;}
    if(r->nodes>=r->limits.nodes){fail(r,"JSON node limit exceeded",true);return NULL;}
    if(!space(r)||r->at==r->input.len){fail(r,"expected JSON value",false);return NULL;}
    if(!charge(r,1))return NULL;
    JsonValue *v=ARENA_NEW(r->arena,JsonValue);r->nodes++;v->offset=r->at;
    char c=r->input.ptr[r->at];
    if(c=='"'){v->kind=JR_STRING;if(!string(r,&v->text))return NULL;}
    else if(c=='-'||digit(c)){v->kind=JR_NUMBER;if(!number(r,&v->text))return NULL;}
    else if(c=='['||c=='{') {
        v->kind=c=='['?JR_ARRAY:JR_OBJECT;char end=c=='['?']':'}';
        if(!take(r)||!space(r))return NULL;
        JsonValue **tail=&v->child;
        if(r->at<r->input.len&&r->input.ptr[r->at]==end){if(!take(r))return NULL;}
        else for(;;) {
            Str name=STR_EMPTY;
            if(v->kind==JR_OBJECT) {
                if(r->at==r->input.len||r->input.ptr[r->at]!='"'){fail(r,"expected member name",false);return NULL;}
                if(!string(r,&name))return NULL;
                for(JsonValue *old=v->child;old;old=old->next) {
                    if(!charge(r,1))return NULL;
                    if(old->name.len==name.len){if(!charge(r,name.len))return NULL;
                        if(str_eq(old->name,name)){fail(r,"duplicate decoded member name",false);return NULL;}}
                }
                if(!space(r))return NULL;
                if(r->at==r->input.len||r->input.ptr[r->at]!=':'){fail(r,"expected colon",false);return NULL;}
                if(!take(r))return NULL;
            }
            JsonValue *child=value(r,depth+1);if(!child)return NULL;
            child->name=name;*tail=child;tail=&child->next;v->count++;
            if(!space(r))return NULL;
            if(r->at==r->input.len){fail(r,"unterminated container",false);return NULL;}
            if(r->input.ptr[r->at]==end){if(!take(r))return NULL;break;}
            if(r->input.ptr[r->at]!=','){fail(r,"expected comma or closing delimiter",false);return NULL;}
            if(!take(r)||!space(r))return NULL;
        }
    } else {
        const char *literal=NULL;
        if(c=='t'){literal="true";v->kind=JR_BOOL;v->boolean=true;}
        else if(c=='f'){literal="false";v->kind=JR_BOOL;}
        else if(c=='n'){literal="null";v->kind=JR_NULL;}
        else {fail(r,"unexpected JSON token",false);return NULL;}
        uint32_t n=(uint32_t)strlen(literal);
        if(n>r->input.len-r->at||memcmp(r->input.ptr+r->at,literal,n)){fail(r,"invalid JSON literal",false);return NULL;}
        if(!charge(r,n))return NULL;r->at+=n;
    }
    v->length=r->at-v->offset;return v;
}
JsonValue *json_read(Arena *a,Str input,JsonLimits limits,JsonReadError *error) {
    JsonReadError local={0};if(!error)error=&local;*error=(JsonReadError){0};
    Reader r={.arena=a,.input=input,.limits=limits,.error=error};
    /* Bound stack depth even when callers supply a more permissive policy. */
    if(!a||(input.len&&!input.ptr)||!limits.depth||limits.depth>128) {
        fail(&r,"invalid JSON reader configuration",false);return NULL;}
    if(input.len>limits.bytes){fail(&r,"JSON byte limit exceeded",true);return NULL;}
    JsonValue *v=value(&r,1);if(!v||!space(&r))return NULL;
    if(r.at!=input.len){fail(&r,"trailing JSON input",false);return NULL;}return v;
}
JsonValue *json_member(const JsonValue *v,const char *name) {
    if(!v||v->kind!=JR_OBJECT)return NULL;
    for(JsonValue *p=v->child;p;p=p->next)if(str_eq_c(p->name,name))return p;return NULL;
}
bool json_u64(const JsonValue *v,uint64_t max,uint64_t *out) {
    if(!v||v->kind!=JR_NUMBER||!v->text.len||!out)return false;
    uint64_t n=0;
    for(uint32_t i=0;i<v->text.len;i++) {char c=v->text.ptr[i];if(!digit(c))return false;
        uint64_t d=(uint64_t)(c-'0');if(d>max||n>(max-d)/10)return false;n=n*10+d;}
    *out=n;return true;
}
