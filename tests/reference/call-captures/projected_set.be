module reference.call_capture.projected_set
struct R { x: i32 }
struct P { child: R }
fn fill(set r: R, value: i32) { r = R{x: value} }
fn replace(inout p: P) -> i32 { p = P{child: R{x: 9}}
    return 7 }
test "projected set cannot survive parent replacement" {
    var p = P{child: R{x: 1}}
    fill(set p.child, replace(inout p))
}
