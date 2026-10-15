module reference.call_capture.selection_index
struct R { x: i32 }
fn observe(let r: R, tag: i32) -> i32 { return r.x }
fn replace(inout xs: [R; 2]) -> i32 { xs = [R{x: 9}, R{x: 8}]
    return 0 }
test "index selection cannot replace its captured parent" {
    var xs = [R{x: 1}, R{x: 2}]
    assert(observe(xs[replace(inout xs)], 0) == 1)
}
