# P5: focused tablet destruction — October 14, 2026

This is a separate case from [ordinary closing](P5_TABLET_CLOSE_2026_10_14.md#actual-ordinary-close-passes). Its starting point is the actual verified activation candidate, with the tablet FOCUSED and its UI open. Closing first would skip the cleanup behavior this case needs to establish.

The native probe is being prepared in `build/player-tablet-focused-destruction-native-20261014-v1`. Its source contract defines a fresh current identity, ownership, UI and replication-authority check before one ordinary `SCR_EntityHelper.DeleteEntityAndChildren(item)` request. It does not manually invoke `OnDelete` or retry deletion.

The isolated callback wrapper records genuine `OnDelete` entry, the existing service hooks for UI Close and conditional screen Destroy, the original pre-super marker, and return through a static recorder using only an integer token. After the superclass returns, the wrapper does not access the receiver or owner. The later observer checks only whether the unchanged weak item, gadget and tablet bindings are available, between checks of the surviving fixture/player context. It performs no candidate getter after the deletion request.

Acceptance will require the exact ordered cleanup evidence and the later unavailable weak bindings. A returned helper, a returned callback or a null binding alone cannot pass. Null bindings do not establish allocator reclamation, absence of delayed work or remote-client deletion. The prior activation and insertion records remain sealed and independently checked.

Review corrected one observation-order mismatch before execution: weak item/gadget presence had initially been evaluated as call arguments before the first surviving-context guard. All three presence samples now occur between the guards. This was an evidence-ordering correction; no engine run or failure result was associated with the draft.

The final trace retains the actual service code on entry and exit, so consumers can independently detect a mismatched pair. Void-result exits remain distinct from calls that did not return. Unexpected service codes are retained and cannot satisfy cleanup acceptance.

The first [native source-guard run](../../build/oct14-destruction-native-source-tests.json) passed 59/60, receipt `b2f34206ecbfa847b0a33a7215eb4abe55d081fe1c53269490fb61e9a4037082`. The conditional-super mutant removed an indentation-specific substring that the test extractor itself required, causing an exception before the intended rejection predicate ran. The failure was in the checker. The failed source/test inputs and receipt remain under `build/player-tablet-focused-destruction-source-failed-20261014-v1`.

The corrected extractor locates a single bare superclass call or an absent sentinel while keeping the separate unconditional-call requirement strict. Added missing and duplicate-call mutants also reject. The [new source receipt](../../build/oct14-destruction-native-source-tests-v2.json) passes 62/62, SHA-256 `1575009058e74dbbfcc846a299338ebfb898373fd34a2b3e5c84cf48aa68c04a`. These are source provenance and guard checks, not executed Enforce semantics; the native implementation did not change for the extractor repair.

At this checkpoint, independent Python/PowerShell consumers are being completed. Engine compilation and actual focused destruction remain unverified. The [source proposal](../../build/player-tablet-focused-destruction-design-20261014-v1/PROPOSAL.md) and [typed record contract](../../build/player-tablet-focused-destruction-native-20261014-v1/destruction-contract.json) describe the precise experimental scope; neither is an execution receipt.

Physical stow, direct active-stow, input bindings, rendered interaction, deferred UI work, repeated lifecycles, dedicated clients and promotion remain separate gates.
