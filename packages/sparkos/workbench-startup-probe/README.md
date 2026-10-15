# Isolated Workbench startup readiness diagnostic

This experimental fixture asks one question: does a fresh owned Workbench process,
using one explicitly selected installed opening profile, expose the exact
prepared addon world as a valid edit-mode world through native APIs and NetAPI?
It does not request play, spawn, callbacks, tablet services, saving, installation,
or a fallback resource opener.

The profiles are `--opening-mechanism startup-cli` (the preserved default),
`--opening-mechanism netapi-resource`, and
`--opening-mechanism module-netapi-resource`, plus
`--opening-mechanism module-netapi-registered`. Each attempt records its selected
CLI profile and distinct wire mechanism (`startup_cli`, `native_netapi`, or
`module_native_netapi`, or `module_registered_netapi`). They are separate experiments. A failure never switches
profiles, retries a native
opening request, or invokes a script opener.

The source-controlled handler is `BerylStartupReadiness`. Its only action is
`observe`. It resolves the addon world through `Workbench.GetAbsolutePath`,
checks its exact registered resource name and native path roundtrip, and observes
WorldEditor module/API, world path, world presence, and edit/game/play modes.
Missing module/API/world readiness remains pending within the fixed budget.
Foreign world or mode observations fail. No script opener or deferred worker is
called by this handler.

`scripts/verify-workbench-startup.py` requires an explicitly hashed successful
callback **prepare-only** receipt. It validates the retained original artifact
and eight prepared source/resource files, copies their exact bytes into a fresh
owned build directory, and adds the ninth read-only startup handler. The copied
callback handler remains dormant and is never invoked by this diagnostic. Its
historical resource-opening code is not a second startup route.

The world serialization remains an experimental `GenericWorldEntity` fixture.
An exact successful native readiness observation would establish only this
fixture/configuration. Earlier resource-opener timeouts, a rejected empty
`SubScene`, or a successful script compile do not establish that readiness.

The default startup CLI launcher uses an explicit argument vector:

```text
-gproj <owned-addon/addon.gproj>
-noOpenLastResource
-scriptAuthorizeAll
-wbmodule=WorldEditor
-run
-load worlds/BerylCallbackProbe.ent
```

The existing authorization argument is retained from the installed Workbench
bridge. This fixture does not modify system or application security settings.
Startup loading is the tested alternative to the prior script-opening request;
neither CLI resource spelling nor asynchronous native completion is presumed.

The alternative `netapi-resource` launcher uses only the established daemon
arguments `-gproj <owned-addon/addon.gproj> -noOpenLastResource -scriptAuthorizeAll`.
After the one health request and loaded-addon check, it performs a read-only
preliminary handler observation that proves exact native addon resolution,
registered resource name, and absolute roundtrip, with no foreign world or play
mode. It then makes **one** built-in `OpenResource` request whose documented
`ResourceName` parameter is the verified owned absolute world path. The raw
native `Opened` outcome is preserved; exact Boolean or integer 0/1 normalization
is recorded separately. Refusal, malformed outcome, timeout, or transport
failure ends the attempt. Acceptance of that request alone is insufficient:
subsequent read-only observations must prove exact owned edit-world readiness.

The prior default attempt `6lzpapeq` compiled cleanly and its log recorded world
loading at approximately 72 ms, but NetAPI did not expose an owned listener
during 42 metadata checks within the 30-second startup stage. Cleanup was
confirmed and no RPC ran. This is transport unavailability for that attempt;
it is not a general claim about WorldEditor or world serialization. The native
NetAPI profile remains an unverified alternative until its own complete receipt
establishes readiness.

The actual native profile attempt `mg5x7fk8` compiled cleanly and passed owned
listener, health, loaded-addon, and preliminary native resource checks. Its one
built-in `OpenResource` request returned `Opened:true`. All 64 following
read-only responses remained pending: the module handle existed, its API was
null, and the observed world path stayed empty. No world-load entry was found
in the retained logs; cleanup was confirmed without evidence errors. Native
request acceptance did not establish world readiness. The reason for the null
API is unresolved.

The third `module-netapi-resource` profile requests module activation at process
startup, separately from resource loading. Its exact six arguments are:

```text
-gproj <owned-addon/addon.gproj>
-noOpenLastResource
-scriptAuthorizeAll
-wbmodule=WorldEditor
-run
```

It deliberately has no `-load` argument. After listener/health/loaded-addon
checks, it follows precisely the same preliminary native identity proof, one
native `OpenResource` request, and strict read-only readiness checks as the
ordinary native profile. Installed `Page_CLI.html` separately documents `-run`
as opening the selected module (line 411) and `-load` as loading a resource at
startup (line 413); line 387 requires `-run` after the module selector to launch
it. This supports an isolated activation experiment, not guaranteed module/API
readiness or an explanation of the preceding failures. No script `OpenModule`
request, extra resource request, or changed timeout is introduced.

The actual third-profile attempt `c3kcvxx_` compiled cleanly and exposed a healthy
owned NetAPI session. Its read-only preliminary and subsequent observations
showed a present WorldEditor API, edit mode, and a non-null world, but the world
path remained empty. The one absolute-path `OpenResource` request returned
`Opened:true` in approximately 46 ms; all 64 following observations stayed
pending and no world-load entry was found in the retained logs. Cleanup was
confirmed. This receipt establishes API availability in that configuration,
not selection or loading of the owned world.

The fourth `module-netapi-registered` profile is a final isolated input-spelling
experiment. It uses the same six startup arguments and native opening sequence
as the third profile. Its only opening-request difference is the exact string:

```text
ResourceName = {BCCBA11B20261008}worlds/BerylCallbackProbe.ent
```

Before that one request, the existing read-only observation must prove that
native `Workbench.GetResourceName` returns this exact registered identifier and
its resource path resolves back to the pinned owned absolute world. No arbitrary
GUID, relative name, alternate path, or extra request is admitted. The installed
`Page_NetApi.html` documents a string resource-file name parameter (line 148)
and an `Opened` Boolean result (line 152). It does not guarantee GUID-string
acceptance or native completion semantics. The fourth profile remains an
unverified hypothesis until its own exact world/API/mode receipt passes. It
never falls back to the third profile's absolute spelling.

Ownership requires a fresh process, the existing shared session mutex, and exact
PID/start/executable checks at every RPC boundary. Listener metadata must name
that owned PID before the single health request. Listener existence establishes
transport readiness only. Health and loaded-addon checks precede read-only
world observations. A failed RPC ends the attempt; no failed call is retried
into success.

Budgets remain 30 seconds per stage, 8 seconds per RPC, 180 seconds overall, and
5 seconds for confirmed owned-process exit. Native launch/bridge calls are not
hard cancellable at their installed boundary; the enclosing owned host job has
its own 240-second limit. The launcher uses PS7 `ProcessStartInfo.ArgumentList`,
hidden window settings, and no shell argument composition. It does not reuse or
stop an unrelated process.

Raw RPC `Raw`/`Response` objects remain unchanged. A separate explicit bool/0/1
codec supplies normalized handler responses. Successful validation binds the
receipt to the frozen adapter hash, exact manifest and nine source files,
native engine/tool identities, complete ownership checks, strict readiness
response, and confirmed cleanup. Only the root `resourceDatabase.rdb`, bounded
to 8 MiB, is admitted as an engine-derived noninput. Retained raw logs are
bounded to 64 MiB in aggregate and captured after owned cleanup.

Prepare without launching any compiler or engine:

```text
python scripts/verify-workbench-startup.py --prepared-receipt <receipt> --expect-prepared-sha256 <hash> --prepare-only
```

The parent integration owner supplies all explicit compiler, PowerShell, engine,
and plugin paths before selecting `--engine-stage compile` or `runtime`. Runtime
performs headless compilation first, then one fresh owned startup attempt. The
configured compiler is fingerprinted but is not executed by this helper because
it reuses exact generated bytes from the selected prepared artifact.

`--self-test` uses inert filesystem trees and malformed synthetic receipts. Its
149 fixed cases cover source/artifact identity, wire types, exact readiness,
arguments, deadlines, ownership, logs, scope, adapter/manifest linkage, and the
derived database. The profiles have exact argument and RPC-order tests;
native opening tests reject missing/duplicate/reordered requests, incorrect
parameters, refused or malformed outcomes, broken raw/normalized linkage, and
missing preliminary identity. Third-profile tests preserve the original cases
and reject startup loading, missing module/run arguments, reordered arguments,
wrong wire/profile/scope, a missing opener, and cross-profile receipt reuse.
The fourth profile adds exact registered-name parameter and native preliminary
identity tests, rejection of absolute/relative/foreign identifiers and extra
parameters, unchanged six-argument checks, and cross-profile receipt rejection.
Those tests launch no PowerShell adapter,
compiler, or engine.
Six declared readiness case IDs are verification observations, not engine-
delivered callback cases. All tablet, callback, multiplayer, visual, and
performance gates remain separate.
