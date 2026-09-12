module reference.destination.sink_boundary
struct R { x: i32 }
fn consume(sink r: R) -> i32 { return r.x }
test "moving the ancestor invalidates a selected destination" {
    var r = R{x: 1}
    r.x = consume(sink r)
}
