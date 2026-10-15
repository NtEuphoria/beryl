# Tablet lifecycle protocol prototype

This package contains experimental Beryl decision logic and a bounded scripted
fixture. It is not an Enfusion component, a generated gadget, or a complete tablet
port. It creates no live resources and requires no model API.

`src/lifecycle.be` defines shared `State { mode, telemetry_accumulator }` and a
separate `Operation` for each synchronous invocation. `next(inout state, inout
operation, reply)` yields one scalar opcode. The host services it immediately,
optionally reenters using a fresh operation and the same current state, then
resumes the original operation. This is a test protocol, not asynchronous work,
a deferred action list, or a production engine interface.

`oracle.py` separately transcribes the retained component's decisions.
`protocol_model.py` schedules scalar responses and records replay transcripts.
The verifier compares their ordered observations, then executes the actual
Beryl functions through the independent reference backend. Engine services are
scripted in Python; their real retention, authority, queued-callback and teardown
contracts remain unverified.

Run `scripts/verify-tablet-lifecycle.py --beryl <identified-compiler> --expect-sha256
<full-hash>` with the configured local Python. The compiler hash must match before
anything executes. Reference execution is the default. Optional `--native
--clang <identified-clang>` requests one differential attempt; a blocked launch
remains incomplete and is not retried. Each attempt receives a new evidence
directory under `build/tablet-lifecycle-*`.

The fixture preserves the original first-open keybind ordering: widgets and
hints are built before the input and keybind setters. The later setter does not
refresh those hints. Any correction belongs to a separately specified behavior
change.

See `docs/advanced/P5_TABLET_LIFECYCLE_PROTOTYPE.md` for the exact contract,
source provenance, verification scope and integration dependencies.
