module reference.destination.compound
struct R { x: i32 }
fn replace(inout r: R) -> i32 { r = R{x: 10}
    return 7 }
test "compound ancestor replacement" {
    var r = R{x: 1}
    r.x += replace(inout r)
    println(r.x)
}
