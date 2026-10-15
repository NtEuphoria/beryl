# Plain member-box state ABI probe

This isolated fixture tests a plain script object's retained state member with
actual Beryl-emitted state classes and handlers. Its local fixture profile is
`plain-script-member-box.bool-i32-f32.v1`; this is a probe label, not a released
compiler or engine capability. It has no tablet, UI, input, authority,
replication, world, prefab, or asset behavior.

The version-2 companion still selects the existing ScriptComponent generation
profile. It generates the real component into the immutable addon, which is
compiled separately alongside the trusted probe. The runtime probe does not
construct, retrieve, or call that component. Its success cannot establish the
component's actual retained state or callback behavior.

The original zero-argument generated component constructor failed a separate
headless compile. After the renderer was repaired to use a member initializer,
an isolated probe attempted `new Bridge(null, null, null)` following documented
derived-component parameter types. That engine attempt rejected all eleven
constructions with `Method SPK_BerylComponentStateProbe is private`. Both attempts
remain preserved failures. This fixture does not add a public component
constructor or bypass engine component construction. Real component instances
and callback delivery need a separate verified prefab/world route.

The trusted `MemberBox` has one `protected ref ActualState m_BerylState = new
ActualState()` member, matching the storage expression under investigation.
`State` defaults are independently specified: `true`, `17`, and `0.125`.
Field mutation preserves the storage object; whole-record assignment and reset
must replace the caller's member with a distinct logical value. Prior references
deliberately keep old storage alive for content/identity checks. Two plain boxes
must have separate state. There are no component constructor/lifecycle claims.

Manual frame operations call the exact emitted `on_frame` holder and method
resolved from the compiler's source-map linkage. Init/delete cases likewise
call emitted handlers directly. No `EOnFrame`, `OnPostInit`, `OnDelete`,
superclass, or event-mask method is invoked on an engine component.

The nested-call case holds a handwritten target `out State` argument while
calling the emitted frame handler, then completes a field update. It probes
the target ABI under a scripted nested call. It does not prove spontaneous
engine reentry or authorize a Beryl engine call across an active access. The
tablet continuation design still returns from Beryl before invoking services.
Nested root replacement during an active borrowed call is outside this fixture.

All float values are exactly representable binary32 constants. The script checks
scalar equality in the target and sends the Boolean outcome; it does not encode
float bits or rely on rounded textual output. The independent manifest lists
eleven expected cases, 73 checks and 95 ordered trace rows. Missing, duplicate,
reordered, partial or extra results fail verification.

The companion declares base-game dependency `58D0FB3206B6F859`, observed in the
retained MESH `addon.gproj`. The harness builds through an explicitly selected
private compiler, preserves the complete original artifact and input identities,
and adds the trusted script to a separately checked isolated addon copy. It
never repairs generated files or edits the generated project.

The first mode is `--prepare-only`: source checks/generation, no native program
or engine launch. Optional engine stages require an explicit PowerShell host
and use existing compile/session transports with no execution-policy flags.
The only admitted derived engine file is a new root `resourceDatabase.rdb`,
bounded to 8 MiB and recorded separately from frozen source inputs. No
installation, promotion, policy change or live MESH edit is performed.

Successful member-box probes leave component runtime state, engine-delivered
initialization/FRAME/deletion, owner validity, teardown, service integration,
multiplayer and visual gates open. A real prefab/world scenario must obtain
engine-created components and record those callbacks independently. Editor
source creation and structural prefab validation remain separate evidence.
