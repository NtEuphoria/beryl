module module_proof
use collision.left
use collision_left
use collision.left.SIZE
use shared.value
const BASE: i32 = 99
struct Storage { values: [i32; SIZE] }

// Ordinary function: Workbench must compile this body, not omit it as main/test.
pub fn exercise() -> i32 {
    let p = left.P.make(4)
    let q = collision_left.P{out: 5}
    var copy = p
    copy.out = 20
    let out = p.get()
    let out_ = q.get()
    let _t0 = left.size()
    var storage = Storage{values: [0, 0, 0]}
    storage.values[2] = 7
    let a: f32 = 4
    // An unrelated function called sqrt cannot shadow the built-in.
    let b: f32 = sqrt(a)
    if b != 2 { return -1 }
    if copy.out != 20 { return -2 }
    if p.BerylCopy() != 4 { return -3 }
    if p.foo_bar() != 11 { return -4 }
    if p.FooBar() != 12 { return -5 }
    if collision.left.SIZE != 3 { return -6 }
    return out + out_ + _t0 + value() + storage.values[2]
}
fn main() { println(exercise()) }
test "module behavior" { assert(exercise() == 32) }
