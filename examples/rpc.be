//! A Reforger RPC handler, which is exactly the shape the security model is
//! for: the arguments arrive from a client you do not control.

module mesh.rpc

pub struct Store {
    slots: [i32; 64]
    count: i32 = 0
}

//! Bounds an index the caller supplied. Marking it `@validator` is what tells
//! the taint engine its result is trustworthy.
@validator
pub fn safe_slot(let raw: i32) -> i32 {
    return clamp(raw, 0, 63)
}

//! Server-authoritative: a client must not be able to reach this directly.
@server_only
pub fn Store.commit(inout self, let slot: i32, let value: i32) {
    self.slots[slot] = value
    self.count += 1
}

//! Every parameter here came off the wire.
@untrusted
@server_only
pub fn Store.on_client_update(inout self, let slot: i32, let value: i32) {
    // Bounded first, so the index is trustworthy by the time it is used.
    let safe = safe_slot(slot)
    self.commit(safe, value)
}

pub fn Store.read(let self, let i: i32) -> i32 {
    return self.slots[clamp(i, 0, 63)]
}
