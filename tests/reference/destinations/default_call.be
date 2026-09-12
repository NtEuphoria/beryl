module reference.destination.default_call
struct R { x: i32 }
fn replace(inout r: R, result: i32 = 7) -> i32 {
    r = R{x: 10}
    return result
}
test "mutable explicit argument with expanded default" {
    var r = R{x: 1}
    r.x = replace(inout r)
}
