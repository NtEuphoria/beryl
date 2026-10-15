module reference.call_capture.method_inout
struct R { x: i32 }
struct P { child: R }
fn R.change(inout self, value: i32) { self.x = value }
fn replace(inout p: P) -> i32 { p = P{child: R{x: 9}}
    return 7 }
test "implicit inout receiver cannot survive parent replacement" {
    var p = P{child: R{x: 1}}
    p.child.change(replace(inout p))
}
