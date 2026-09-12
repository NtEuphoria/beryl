/* enforce_backend.h — emits EnforceScript for Arma Reforger's Enfusion engine.
 *
 * The profile lint runs first and refuses what the engine cannot express, so
 * Workbench never sees script that was doomed before it started. That matters
 * because one real error there produces a cascade of phantom ones across
 * untouched base-game files.
 */
#ifndef BERYL_ENFORCE_BACKEND_H
#define BERYL_ENFORCE_BACKEND_H

#include "../common/diag.h"
#include "../sema/resolve.h"

typedef enum { EF_EXPORT_CLASS, EF_EXPORT_METHOD, EF_EXPORT_CONSTRUCTOR } EnfusionExportKind;
typedef struct {
    EnfusionExportKind kind;
    Str source; /* exact qualified declaration */
    Str name;   /* exact engine-facing name */
    Item *item; /* filled by validation */
} EnfusionExport;
typedef VEC(EnfusionExport) EnfusionExports;

typedef struct {
    Str prefix;  /* class-name prefix; Enfusion has no namespaces */
    Str out_dir; /* where the .c files are written */
    Str source_map; /* optional separate JSON sidecar path; requires out_dir */
    EnfusionExports exports;
} EnfusionOpts;

bool enfusion_validate_exports(DiagBag *d, Program *p, EnfusionOpts o);
Str enfusion_export_name(EnfusionExports exports, Item *item);
Item *enfusion_export_constructor(EnfusionExports exports, Item *receiver);

/* Reports every construct the engine cannot represent. Run before emitting. */
bool enfusion_lint(DiagBag *d, Program *p, EnfusionOpts o);

/* Writes one generated script containing all classes. UTF-8 with no BOM. */
bool enfusion_emit(Arena *a, SourceMap *sm, DiagBag *d, Program *p, EnfusionOpts o);

/* Renders a single item to EnforceScript text. Used by the golden tests, so
 * the exact output is pinned rather than merely plausible. */
Str enfusion_render_item(Arena *a, SourceMap *sm, DiagBag *d, Program *p, Item *it,
                         EnfusionOpts o);

/* Renders every item of a program into one buffer, in declaration order. */
Str enfusion_render_all(Arena *a, SourceMap *sm, DiagBag *d, Program *p, EnfusionOpts o);

/* The file name an item is written to, without the directory. */
Str enfusion_file_name(Arena *a, Item *it, EnfusionOpts o);

#endif /* BERYL_ENFORCE_BACKEND_H */
