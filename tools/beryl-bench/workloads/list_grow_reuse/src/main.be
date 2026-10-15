//! Push/clear cycles. Capacity is retained across `clear`, so later rounds
//! should not reallocate; Phase 6 `reserve` makes the first round explicit.

module bench.list_grow_reuse

fn main() {
    var xs: List<i32>
    var last: i32 = 0
    for round in 0..2000 {
        for i in 0..256 {
            xs.push(i)
        }
        last = xs.len()
        xs.clear()
    }
    println(last)
    println(xs.len())
}
