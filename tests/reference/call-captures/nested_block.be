module reference.call_capture.nested_block
struct R { x: i32 }
struct P { child: R }
fn observe(let r: R, tag: i32) -> i32 { return r.x }
fn replace(inout p: P) -> i32 {
    { p = P{child: R{x: 9}} }
    return 0
}
test "later helper with a nested statement block cannot replace a captured parent" {
    var p = P{child: R{x: 1}}
    assert(observe(p.child, replace(inout p)) == 1)
}
