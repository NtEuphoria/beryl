module reference.destination.method
struct R { x: i32 }
fn R.replace(inout self) -> i32 { self = R{x: 10}
    return 7 }
test "implicit mutable receiver" {
    var r = R{x: 1}
    r.x = r.replace()
}
