module reference.call_capture.loop_mutation
struct R { x: i32 }
struct P { child: R }
fn observe(let r: R, tag: i32) -> i32 { return r.x }
fn replace(inout p: P) -> i32 {
    var i = 0
    while i < 1 {
        p = P{child: R{x: 9}}
        i += 1
    }
    return 0
}
test "later loop cannot conceal parent replacement" {
    var p = P{child: R{x: 1}}
    assert(observe(p.child, replace(inout p)) == 1)
}
