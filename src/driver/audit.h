/* audit.h — the `beryl audit` report. */
#ifndef BERYL_AUDIT_H
#define BERYL_AUDIT_H

#include "../common/source.h"
#include "../sema/resolve.h"

int audit_report(Program *p, SourceMap *sm, Str package_name, bool forbid_unsafe);

#endif /* BERYL_AUDIT_H */
