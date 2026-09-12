module reference.destination.nested_call
struct R { x: i32 }
fn replace(inout r: R) -> i32 { r = R{x: 10}
    return 7 }
fn wrap(x: i32) -> i32 { return x }
test "nested call effects" {
    var r = R{x: 1}
    r.x = wrap(wrap(replace(inout r)))
}
