# Planned N1a: independent original-source state and screen-service oracle

This package is **source-only**, with no installed scenario or runtime transport.
It does not change production Beryl, the trusted service adapter, N0 callbacks,
the observer, or the active installation. The separate N0 receipt now admits the
native STOWED callback prerequisite; N1a still needs its own immutable candidate,
trusted observation source, compilation, transport gates, and native execution.

`oracle.py` directly models the pinned original `SPK_TabletComponent` public
methods. It does not run Beryl continuation PCs, generated code, or a native
allocation helper. `contract.json` fixes seven case IDs/actions and the original
component/screen, Beryl, and adapter source hashes. `verify_oracle.py` runs only
predeclared Python fixtures and deliberate observation mutants, retaining each
attempt in a new build directory. Synthetic service results are never inserted
into an engine run.

The selected domain starts with two natively initialized component-only owners,
distinct persistent State roots, mode STOWED (0), decoded zero accumulator, and
absent UI/screen. It excludes input, gadget, inventory, editable entity, MeshObject,
Rpl, core, successful Focus, focused frames, reentrant public actions, external
widget/state mutation and invalid owners. Both owners are observed before and
after every action, including the final read-only independence case.

The fixed actions are refused Focus, first held, repeated held, refused Unfocus,
stow, repeated stow, and independence. Public SetHeld is void; its private
continuation result is not a public Boolean result. First/repeated Enable may
normally return FF, FT, or TT. False Enable leaves HELD published. In this live,
non-reentrant domain a prior successful Build retains the same widget, so the
second Enable must reuse it. Observed loss/replacement of a previously nonnull
widget or a TF sequence returns `outside_admitted_domain`/unavailable, rather than
being normalized into a valid false branch or labeled a production semantic bug.
Native object validity is a separate transport/lifetime obligation; scalar tokens
and a nonnull getter do not establish it.

The proposed trusted hooks are declared in the contract. Creation is recorded
only **after actual allocation and publication** in opcode 10; Build is deferred
inside Enable. Each Enable/Disable pair has its own local invocation identifier.
Enable is called exactly once through its original `GetOwner()` expression, its
actual Boolean is captured in a separate local, and the Beryl reply remains
unchanged. Hooks do not share an operation slot, change state, supply fake
references, suppress a call, invoke callbacks, or add a GetOwner evaluation to
that original expression. Hook base bodies may be no-ops; the future trusted
observer assigns scalar tokens by observed identity and supplies read records.

The nine service events are one creation and four enter/exit pairs. The selected
event boundary is the adapter call, so internal Build, Destroy-to-Disable, native
SetRenderTarget and RemoveRenderTarget are not counted. Before/after snapshots
read GetState, GetUI, GetScreen, IsEnabled and GetWidget, plus the protected Beryl
State/accumulator in a reviewed observer. They cannot infer a native owner binding,
pixels, content validity, allocation counts, resource release or internal calls.
A true Enable result and nonnull widget establish only the observed script
service branch. Missing successful Enable leaves screen availability unobserved;
the false normal branch can still preserve and verify the public decisions.

The typed JSON checker requires exact schema/types/identity, ordered seven cases,
contiguous service sequence/pairs, complete snapshots, normal public returns and
the exact checksum. Harness timeout, cancellation, stale input, source trap,
engine exception and incomplete service call do not count as false returns.
Accumulator strings are decoded as finite numeric zero, including `-0`; there is
no binary32 bitwise or signed-zero claim. The checksum binds the exact typed-record
serialization, including its numeric text; this format is a proposal. A later
native flat wire encoder must prove its own field/Boolean/empty-array/checksum
contract and preserve raw replies before this checker is used on engine evidence.

Run the pure gate from the repository root with bundled Python:

```text
python packages/sparkos/tablet-real-service-probe/verify_oracle.py
```

The library also supports `--expected identity.json --verify completion.json`,
which verifies captured records without execution, or `--synthetic FF|FT|TT`,
which labels its output synthetic. The expected source hash is the independently
frozen candidate-input identity, excluding any self-referential sender stamp;
the expected contract hash is the exact `contract.json` bytes. A successful typed
comparison cannot establish native origin. Full transport/process/world/compiled
token/final-stop and source integrity remain separate root-owned gates.

See [the N1 admission packet](../../../docs/advanced/P5_TABLET_REAL_SERVICES_ADMISSION.md).
No result here closes UI, native input, profile ownership, gadget/equipment,
teardown, render-target binding, visual interaction, multiplayer or promotion.
