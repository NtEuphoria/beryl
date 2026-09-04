#include "lexer.h"

#include <stdlib.h>
#include <string.h>


/* ---- token names ------------------------------------------------------- */

static const char *const g_tok_names[TK_COUNT] = {
    [TK_EOF] = "end of file",   [TK_NEWLINE] = "end of line",
    [TK_IDENT] = "identifier",  [TK_INT] = "integer literal",
    [TK_FLOAT] = "float literal", [TK_STRING] = "string literal",
    [TK_CHAR] = "char literal",  [TK_DOC] = "doc comment",

    [TK_MODULE] = "module",     [TK_USE] = "use",
    [TK_PUB] = "pub",           [TK_FN] = "fn",
    [TK_STRUCT] = "struct",     [TK_ENUM] = "enum",
    [TK_TRAIT] = "trait",       [TK_LET] = "let",
    [TK_VAR] = "var",           [TK_IF] = "if",
    [TK_ELSE] = "else",         [TK_WHILE] = "while",
    [TK_FOR] = "for",           [TK_IN] = "in",
    [TK_RETURN] = "return",     [TK_BREAK] = "break",
    [TK_CONTINUE] = "continue", [TK_TEST] = "test",
    [TK_CONST] = "const",       [TK_COMPTIME] = "comptime",
    [TK_TRUE] = "true",         [TK_FALSE] = "false",
    [TK_INOUT] = "inout",       [TK_SINK] = "sink",
    [TK_SET] = "set",           [TK_AS] = "as",
    [TK_TRY] = "try",           [TK_CATCH] = "catch",
    [TK_ORELSE] = "orelse",     [TK_ERROR] = "error",
    [TK_DEFER] = "defer",       [TK_SELF] = "self",
    [TK_MATCH] = "match",

    [TK_LPAREN] = "(",          [TK_RPAREN] = ")",
    [TK_LBRACE] = "{",          [TK_RBRACE] = "}",
    [TK_LBRACKET] = "[",        [TK_RBRACKET] = "]",
    [TK_COMMA] = ",",           [TK_DOT] = ".",
    [TK_DOTDOT] = "..",         [TK_COLON] = ":",
    [TK_SEMI] = ";",
    [TK_ARROW] = "->",          [TK_FATARROW] = "=>",
    [TK_AT] = "@",              [TK_QUESTION] = "?",
    [TK_BANG] = "!",            [TK_PIPE] = "|",
    [TK_AMP] = "&",             [TK_CARET] = "^",
    [TK_TILDE] = "~",           [TK_PLUS] = "+",
    [TK_MINUS] = "-",           [TK_STAR] = "*",
    [TK_SLASH] = "/",           [TK_PERCENT] = "%",
    [TK_ASSIGN] = "=",          [TK_EQ] = "==",
    [TK_NE] = "!=",             [TK_LT] = "<",
    [TK_LE] = "<=",             [TK_GT] = ">",
    [TK_GE] = ">=",             [TK_ANDAND] = "&&",
    [TK_OROR] = "||",           [TK_SHL] = "<<",
    [TK_SHR] = ">>",            [TK_PLUSEQ] = "+=",
    [TK_MINUSEQ] = "-=",        [TK_STAREQ] = "*=",
    [TK_SLASHEQ] = "/=",        [TK_PERCENTEQ] = "%=",
};

const char *tok_name(TokKind k) {
    if ((unsigned)k >= (unsigned)TK_COUNT || !g_tok_names[k]) return "?";
    return g_tok_names[k];
}

/* ---- keyword table ----------------------------------------------------- */

typedef struct {
    const char *text;
    TokKind     kind;
} Keyword;

static const Keyword g_keywords[] = {
    {"module", TK_MODULE},     {"use", TK_USE},         {"pub", TK_PUB},
    {"fn", TK_FN},             {"struct", TK_STRUCT},   {"enum", TK_ENUM},
    {"trait", TK_TRAIT},       {"let", TK_LET},         {"var", TK_VAR},
    {"if", TK_IF},             {"else", TK_ELSE},       {"while", TK_WHILE},
    {"for", TK_FOR},           {"in", TK_IN},           {"return", TK_RETURN},
    {"break", TK_BREAK},       {"continue", TK_CONTINUE}, {"test", TK_TEST},
    {"const", TK_CONST},       {"comptime", TK_COMPTIME}, {"true", TK_TRUE},
    {"false", TK_FALSE},       {"inout", TK_INOUT},     {"sink", TK_SINK},
    {"set", TK_SET},           {"as", TK_AS},           {"try", TK_TRY},
    {"catch", TK_CATCH},       {"orelse", TK_ORELSE},   {"error", TK_ERROR},
    {"defer", TK_DEFER},       {"self", TK_SELF},       {"match", TK_MATCH},
};

static TokKind keyword_lookup(Str s) {
    for (size_t i = 0; i < sizeof g_keywords / sizeof g_keywords[0]; i++) {
        if (str_eq_c(s, g_keywords[i].text)) return g_keywords[i].kind;
    }
    return TK_IDENT;
}

/* ---- newline classification -------------------------------------------- */

bool tok_can_end_expr(TokKind k) {
    switch (k) {
        case TK_IDENT:
        case TK_INT:
        case TK_FLOAT:
        case TK_STRING:
        case TK_CHAR:
        case TK_TRUE:
        case TK_FALSE:
        case TK_SELF:
        case TK_RPAREN:
        case TK_RBRACE:
        case TK_RBRACKET:
        case TK_QUESTION:
        case TK_BREAK:
        case TK_CONTINUE:
        case TK_RETURN: return true;
        default: return false;
    }
}

/* Tokens that continue the previous line rather than starting a statement. */
bool tok_is_continuation(TokKind k) {
    switch (k) {
        case TK_PLUS:
        case TK_MINUS:
        case TK_STAR:
        case TK_SLASH:
        case TK_PERCENT:
        case TK_EQ:
        case TK_NE:
        case TK_LT:
        case TK_LE:
        case TK_GT:
        case TK_GE:
        case TK_ANDAND:
        case TK_OROR:
        case TK_AMP:
        case TK_PIPE:
        case TK_CARET:
        case TK_SHL:
        case TK_SHR:
        case TK_DOT:
        case TK_DOTDOT:
        case TK_AS:
        case TK_COMMA:
        case TK_COLON:
        case TK_ARROW:
        case TK_FATARROW:
        case TK_ASSIGN:
        case TK_PLUSEQ:
        case TK_MINUSEQ:
        case TK_STAREQ:
        case TK_SLASHEQ:
        case TK_PERCENTEQ:
        case TK_RPAREN:
        case TK_RBRACKET:
        case TK_RBRACE:
        case TK_ELSE:
        case TK_CATCH:
        case TK_ORELSE: return true;
        default: return false;
    }
}

/* ---- scanner ----------------------------------------------------------- */

typedef struct {
    Arena      *a;
    SourceMap  *sm;
    DiagBag    *d;
    Interner   *in;
    uint32_t    file;
    const char *base;
    const char *p;
    const char *end;
} Lexer;

typedef struct {
    Token t;
    bool  nl_before;
} RawTok;

typedef VEC(RawTok) RawVec;

static bool at_end(const Lexer *L) { return L->p >= L->end; }
static char peek(const Lexer *L) { return at_end(L) ? '\0' : *L->p; }
static char peek2(const Lexer *L) { return (L->p + 1 >= L->end) ? '\0' : L->p[1]; }

static uint32_t off(const Lexer *L, const char *p) { return (uint32_t)(p - L->base); }

static Span span_at(const Lexer *L, const char *s, const char *e) {
    return (Span){L->file, off(L, s), (uint32_t)(e - s)};
}

static bool is_ident_start(char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_';
}
static bool is_ident_cont(char c) { return is_ident_start(c) || (c >= '0' && c <= '9'); }
static bool is_digit(char c) { return c >= '0' && c <= '9'; }
static bool is_hex(char c) {
    return is_digit(c) || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
}
static int hex_val(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return c - 'A' + 10;
}

static bool valid_num_suffix(Str s) {
    static const char *const ok[] = {"i8",  "i16", "i32", "i64", "u8",
                                     "u16", "u32", "u64", "f32", "f64"};
    for (size_t i = 0; i < sizeof ok / sizeof ok[0]; i++)
        if (str_eq_c(s, ok[i])) return true;
    return false;
}

/* Scans an optional numeric type suffix, reporting BE0104 if it is unknown. */
static Str scan_suffix(Lexer *L) {
    if (!is_ident_start(peek(L))) return STR_EMPTY;
    const char *s = L->p;
    while (is_ident_cont(peek(L))) L->p++;
    Str suf = str_new(s, (uint32_t)(L->p - s));
    if (!valid_num_suffix(suf)) {
        Diag *dg = diag_error(L->d, 104, span_at(L, s, L->p),
                              "unknown numeric suffix `%.*s`", (int)suf.len, suf.ptr);
        diag_help(dg, "valid suffixes are i8 i16 i32 i64 u8 u16 u32 u64 f32 f64");
        return STR_EMPTY;
    }
    return suf;
}

static void scan_radix(Lexer *L, Token *t, const char *start, int base) {
    L->p += 2; /* consume 0x / 0b / 0o */
    uint64_t val   = 0;
    bool     any   = false;
    bool     over  = false;
    while (!at_end(L)) {
        char c = peek(L);
        if (c == '_') {
            L->p++;
            continue;
        }
        int dv;
        if (base == 16) {
            if (!is_hex(c)) break;
            dv = hex_val(c);
        } else if (base == 2) {
            if (c != '0' && c != '1') break;
            dv = c - '0';
        } else {
            if (c < '0' || c > '7') break;
            dv = c - '0';
        }
        if (val > (UINT64_MAX - (uint64_t)dv) / (uint64_t)base) over = true;
        val = val * (uint64_t)base + (uint64_t)dv;
        any = true;
        L->p++;
    }
    if (!any) {
        diag_error(L->d, 104, span_at(L, start, L->p), "numeric literal has no digits");
    } else if (over) {
        diag_error(L->d, 106, span_at(L, start, L->p),
                   "integer literal is too large for a 64-bit value");
    }
    t->kind   = TK_INT;
    t->ival   = val;
    t->suffix = scan_suffix(L);
}

static void scan_number(Lexer *L, Token *t) {
    const char *start = L->p;

    if (peek(L) == '0' && (peek2(L) == 'x' || peek2(L) == 'X')) {
        scan_radix(L, t, start, 16);
        return;
    }
    if (peek(L) == '0' && (peek2(L) == 'b' || peek2(L) == 'B')) {
        scan_radix(L, t, start, 2);
        return;
    }
    if (peek(L) == '0' && (peek2(L) == 'o' || peek2(L) == 'O')) {
        scan_radix(L, t, start, 8);
        return;
    }

    bool is_float = false;
    while (is_digit(peek(L)) || peek(L) == '_') L->p++;

    /* A '.' begins a fraction only when a digit follows, so `1..2` stays an
     * integer followed by the range operator. */
    if (peek(L) == '.' && is_digit(peek2(L))) {
        is_float = true;
        L->p++;
        while (is_digit(peek(L)) || peek(L) == '_') L->p++;
    }
    if (peek(L) == 'e' || peek(L) == 'E') {
        const char *save = L->p;
        L->p++;
        if (peek(L) == '+' || peek(L) == '-') L->p++;
        if (is_digit(peek(L))) {
            is_float = true;
            while (is_digit(peek(L))) L->p++;
        } else {
            L->p = save; /* not an exponent after all */
        }
    }

    /* Strip '_' before handing the text to strtod / manual accumulation. */
    uint32_t raw_len = (uint32_t)(L->p - start);
    char    *buf     = (char *)arena_alloc(L->a, raw_len + 1, 1);
    uint32_t n       = 0;
    for (uint32_t i = 0; i < raw_len; i++)
        if (start[i] != '_') buf[n++] = start[i];
    buf[n] = '\0';

    if (is_float) {
        t->kind = TK_FLOAT;
        t->fval = strtod(buf, NULL);
    } else {
        uint64_t val  = 0;
        bool     over = false;
        for (uint32_t i = 0; i < n; i++) {
            uint64_t dv = (uint64_t)(buf[i] - '0');
            if (val > (UINT64_MAX - dv) / 10u) over = true;
            val = val * 10u + dv;
        }
        if (over)
            diag_error(L->d, 106, span_at(L, start, L->p),
                       "integer literal is too large for a 64-bit value");
        t->kind = TK_INT;
        t->ival = val;
    }
    t->suffix = scan_suffix(L);

    /* A suffix may retroactively make an integer literal a float, e.g. 1f32. */
    if (t->kind == TK_INT && (str_eq_c(t->suffix, "f32") || str_eq_c(t->suffix, "f64"))) {
        t->kind = TK_FLOAT;
        t->fval = (double)t->ival;
    }
}

/* Reads one escape sequence after the backslash. Returns the scalar value. */
static uint32_t scan_escape(Lexer *L, bool *ok) {
    *ok           = true;
    const char *s = L->p - 1; /* the backslash */
    char        c = peek(L);
    L->p++;
    switch (c) {
        case 'n': return '\n';
        case 't': return '\t';
        case 'r': return '\r';
        case '0': return '\0';
        case '\\': return '\\';
        case '"': return '"';
        case '\'': return '\'';
        case 'x': {
            if (!is_hex(peek(L)) || !is_hex(peek2(L))) {
                diag_error(L->d, 103, span_at(L, s, L->p),
                           "`\\x` must be followed by exactly two hex digits");
                *ok = false;
                return 0;
            }
            int v = hex_val(peek(L)) * 16 + hex_val(peek2(L));
            L->p += 2;
            return (uint32_t)v;
        }
        default: {
            Diag *dg = diag_error(L->d, 103, span_at(L, s, L->p),
                                  "unknown escape sequence `\\%c`", c ? c : '?');
            diag_help(dg, "supported escapes are \\n \\t \\r \\0 \\\\ \\\" \\' \\xNN");
            *ok = false;
            return 0;
        }
    }
}

static void scan_string(Lexer *L, Token *t) {
    const char *open = L->p;
    L->p++; /* opening quote */

    SB sb;
    sb_init(&sb, L->a);
    while (!at_end(L) && peek(L) != '"' && peek(L) != '\n') {
        if (peek(L) == '\\') {
            L->p++;
            bool     ok = true;
            uint32_t v  = scan_escape(L, &ok);
            if (ok) sb_char(&sb, (char)v);
        } else {
            sb_char(&sb, peek(L));
            L->p++;
        }
    }
    if (at_end(L) || peek(L) != '"') {
        diag_error(L->d, 101, span_at(L, open, open + 1), "unterminated string literal");
    } else {
        L->p++; /* closing quote */
    }
    t->kind = TK_STRING;
    t->text = sb_finish(&sb);
}

static void scan_raw_string(Lexer *L, Token *t) {
    const char *open = L->p; /* at the 'r' */
    L->p += 2;               /* r" */
    const char *s = L->p;
    while (!at_end(L) && peek(L) != '"' && peek(L) != '\n') L->p++;
    Str body = str_new(s, (uint32_t)(L->p - s));
    if (at_end(L) || peek(L) != '"')
        diag_error(L->d, 101, span_at(L, open, open + 2), "unterminated raw string literal");
    else L->p++;
    t->kind = TK_STRING;
    t->text = body;
}

static void scan_char(Lexer *L, Token *t) {
    const char *open = L->p;
    L->p++; /* opening quote */

    uint32_t v = 0;
    if (peek(L) == '\\') {
        L->p++;
        bool ok = true;
        v       = scan_escape(L, &ok);
    } else if (!at_end(L) && peek(L) != '\'' && peek(L) != '\n') {
        v = (unsigned char)peek(L);
        L->p++;
    } else {
        diag_error(L->d, 102, span_at(L, open, L->p), "empty character literal");
    }

    if (at_end(L) || peek(L) != '\'') {
        diag_error(L->d, 102, span_at(L, open, open + 1), "unterminated character literal");
    } else {
        L->p++;
    }
    t->kind = TK_CHAR;
    t->ival = v;
}

/* Skips spaces, tabs and carriage returns. Returns true if a newline was
 * crossed (comments count as transparent). */
static bool skip_trivia(Lexer *L, RawVec *out) {
    bool saw_nl = false;
    for (;;) {
        char c = peek(L);
        if (c == ' ' || c == '\t' || c == '\r') {
            L->p++;
        } else if (c == '\n') {
            saw_nl = true;
            L->p++;
        } else if (c == '/' && peek2(L) == '/') {
            const char *s = L->p;
            L->p += 2;
            bool is_doc = (peek(L) == '!');
            if (is_doc) L->p++;
            const char *tx = L->p;
            while (!at_end(L) && peek(L) != '\n') L->p++;
            if (is_doc) {
                RawTok r  = {0};
                r.t.kind  = TK_DOC;
                r.t.span  = span_at(L, s, L->p);
                r.t.text  = str_new(tx, (uint32_t)(L->p - tx));
                r.nl_before = saw_nl;
                vec_push(L->a, *out, r);
                saw_nl = false;
            }
        } else if (c == '/' && peek2(L) == '*') {
            const char *s = L->p;
            L->p += 2;
            Diag *dg = diag_error(L->d, 107, span_at(L, s, L->p),
                                  "block comments are not supported");
            diag_help(dg, "use `//` line comments; they nest predictably and read better "
                          "in diffs");
            /* Consume to the end of the line so one mistake is one error. */
            while (!at_end(L) && peek(L) != '\n') L->p++;
        } else {
            return saw_nl;
        }
    }
}

static void punct(Lexer *L, Token *t, TokKind k, int len) {
    const char *s = L->p;
    L->p += len;
    t->kind = k;
    t->span = span_at(L, s, L->p);
}

TokenVec lex_file(Arena *a, SourceMap *sm, DiagBag *d, Interner *in, uint32_t file) {
    SourceFile *sf = srcmap_get(sm, file);
    Lexer       L  = {a, sm, d, in, file, sf->text.ptr, sf->text.ptr,
                      sf->text.ptr + sf->text.len};

    RawVec raw = {0};

    for (;;) {
        bool nl = skip_trivia(&L, &raw);
        if (at_end(&L)) {
            RawTok r    = {0};
            r.t.kind    = TK_EOF;
            r.t.span    = span_at(&L, L.p, L.p);
            r.nl_before = nl;
            vec_push(a, raw, r);
            break;
        }

        RawTok r      = {0};
        r.nl_before   = nl;
        const char *s = L.p;
        char        c = peek(&L);

        if (is_ident_start(c)) {
            if (c == 'r' && peek2(&L) == '"') {
                scan_raw_string(&L, &r.t);
                r.t.span = span_at(&L, s, L.p);
            } else {
                while (is_ident_cont(peek(&L))) L.p++;
                Str word  = intern(in, str_new(s, (uint32_t)(L.p - s)));
                r.t.kind  = keyword_lookup(word);
                r.t.text  = word;
                r.t.span  = span_at(&L, s, L.p);
            }
        } else if (is_digit(c)) {
            scan_number(&L, &r.t);
            r.t.span = span_at(&L, s, L.p);
        } else if (c == '"') {
            scan_string(&L, &r.t);
            r.t.span = span_at(&L, s, L.p);
        } else if (c == '\'') {
            scan_char(&L, &r.t);
            r.t.span = span_at(&L, s, L.p);
        } else {
            char n = peek2(&L);
            switch (c) {
                case '(': punct(&L, &r.t, TK_LPAREN, 1); break;
                case ')': punct(&L, &r.t, TK_RPAREN, 1); break;
                case '{': punct(&L, &r.t, TK_LBRACE, 1); break;
                case '}': punct(&L, &r.t, TK_RBRACE, 1); break;
                case '[': punct(&L, &r.t, TK_LBRACKET, 1); break;
                case ']': punct(&L, &r.t, TK_RBRACKET, 1); break;
                case ',': punct(&L, &r.t, TK_COMMA, 1); break;
                case ':': punct(&L, &r.t, TK_COLON, 1); break;
                case ';': punct(&L, &r.t, TK_SEMI, 1); break;
                case '@': punct(&L, &r.t, TK_AT, 1); break;
                case '?': punct(&L, &r.t, TK_QUESTION, 1); break;
                case '~': punct(&L, &r.t, TK_TILDE, 1); break;
                case '^': punct(&L, &r.t, TK_CARET, 1); break;
                case '.': punct(&L, &r.t, n == '.' ? TK_DOTDOT : TK_DOT, n == '.' ? 2 : 1); break;
                case '+': punct(&L, &r.t, n == '=' ? TK_PLUSEQ : TK_PLUS, n == '=' ? 2 : 1); break;
                case '-':
                    if (n == '>') punct(&L, &r.t, TK_ARROW, 2);
                    else if (n == '=') punct(&L, &r.t, TK_MINUSEQ, 2);
                    else punct(&L, &r.t, TK_MINUS, 1);
                    break;
                case '*': punct(&L, &r.t, n == '=' ? TK_STAREQ : TK_STAR, n == '=' ? 2 : 1); break;
                case '/': punct(&L, &r.t, n == '=' ? TK_SLASHEQ : TK_SLASH, n == '=' ? 2 : 1); break;
                case '%': punct(&L, &r.t, n == '=' ? TK_PERCENTEQ : TK_PERCENT, n == '=' ? 2 : 1); break;
                case '=':
                    if (n == '=') punct(&L, &r.t, TK_EQ, 2);
                    else if (n == '>') punct(&L, &r.t, TK_FATARROW, 2);
                    else punct(&L, &r.t, TK_ASSIGN, 1);
                    break;
                case '!': punct(&L, &r.t, n == '=' ? TK_NE : TK_BANG, n == '=' ? 2 : 1); break;
                case '<':
                    if (n == '=') punct(&L, &r.t, TK_LE, 2);
                    else if (n == '<') punct(&L, &r.t, TK_SHL, 2);
                    else punct(&L, &r.t, TK_LT, 1);
                    break;
                case '>':
                    if (n == '=') punct(&L, &r.t, TK_GE, 2);
                    else if (n == '>') punct(&L, &r.t, TK_SHR, 2);
                    else punct(&L, &r.t, TK_GT, 1);
                    break;
                case '&': punct(&L, &r.t, n == '&' ? TK_ANDAND : TK_AMP, n == '&' ? 2 : 1); break;
                case '|': punct(&L, &r.t, n == '|' ? TK_OROR : TK_PIPE, n == '|' ? 2 : 1); break;
                default: {
                    L.p++;
                    diag_error(d, 105, span_at(&L, s, L.p), "unexpected character `%c`", c);
                    continue;
                }
            }
        }
        vec_push(a, raw, r);
    }

    /* ---- second pass: turn line breaks into statement terminators ------- */

    TokenVec out   = {0};
    int      depth = 0;
    TokKind  prev  = TK_EOF;

    for (uint32_t i = 0; i < raw.len; i++) {
        Token  t = raw.data[i].t;
        TokKind k = t.kind;

        if (raw.data[i].nl_before && depth == 0 && tok_can_end_expr(prev) &&
            !tok_is_continuation(k) && prev != TK_EOF) {
            Token nlt = {0};
            nlt.kind  = TK_NEWLINE;
            nlt.span  = (Span){file, t.span.offset, 0};
            vec_push(a, out, nlt);
        }

        if (k == TK_LPAREN || k == TK_LBRACKET) depth++;
        else if (k == TK_RPAREN || k == TK_RBRACKET) {
            if (depth > 0) depth--;
        }

        t.nl_before = raw.data[i].nl_before;
        vec_push(a, out, t);
        if (k != TK_DOC) prev = k;
    }

    return out;
}
