module reference.call_capture.method_receiver
struct R { x: i32 }
struct P { child: R }
fn R.observe(let self, tag: i32) -> i32 { return self.x }
fn replace(inout p: P) -> i32 { p = P{child: R{x: 9}}
    return 0 }
test "implicit let receiver cannot survive parent replacement" {
    var p = P{child: R{x: 1}}
    assert(p.child.observe(replace(inout p)) == 1)
}
