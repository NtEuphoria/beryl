module reference.destination.unreachable
struct R { x: i32 }
fn replace(inout r: R) -> i32 { r = R{x: 10}
    return 7 }
test "unreachable conflict" {
    var r = R{x: 1}
    return
    r.x = replace(inout r)
}
