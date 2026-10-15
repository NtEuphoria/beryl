module reference.call_capture.sink_temporary
struct R { x: i32 }
fn observe(let r: R, sink other: R) -> i32 { return r.x + other.x }
fn make(value: i32) -> R { return R{x: value} }
test "independent sink rvalues do not consume borrowed storage" {
    var r = R{x: 1}
    let literal_got = observe(r, sink R{x: 7})
    let returned_got = observe(r, sink make(3))
    assert(literal_got == 8)
    assert(returned_got == 4)
    assert(r.x == 1)
    println(literal_got)
    println(returned_got)
}
