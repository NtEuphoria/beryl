module reference.call_capture.nested_set
struct R { x: i32 }
fn observe(let r: R, tag: i32) -> i32 { return r.x }
fn fill(set x: i32) -> i32 { x = 9
    return 0 }
test "later set helper cannot mutate a captured record" {
    var r = R{x: 1}
    assert(observe(r, fill(set r.x)) == 1)
}
