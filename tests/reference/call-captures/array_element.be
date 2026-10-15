module reference.call_capture.array_element
struct R { x: i32 }
fn observe(let r: R, tag: i32) -> i32 { return r.x }
fn replace(inout xs: [R; 2]) -> i32 { xs = [R{x: 9}, R{x: 8}]
    return 0 }
test "array element borrow cannot survive root replacement" {
    var xs = [R{x: 1}, R{x: 2}]
    assert(observe(xs[0], replace(inout xs)) == 1)
}
