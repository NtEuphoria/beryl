//! Non-overflowing checked i32 chain. Historical LCG overflowed on its first
//! multiply; this kernel stays inside i32 so a trap is a compiler bug.

module bench.checked_lcg

fn main() {
    var x: i32 = 1
    for i in 0..20000000 {
        x = x + 2
        x = x - 1
    }
    println(x)
}
