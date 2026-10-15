module reference.call_capture.projected_inout
struct R { x: i32 }
struct P { child: R }
fn change(inout r: R, value: i32) { r.x = value }
fn replace(inout p: P) -> i32 { p = P{child: R{x: 9}}
    return 7 }
test "projected inout cannot survive parent replacement" {
    var p = P{child: R{x: 1}}
    change(inout p.child, replace(inout p))
}
