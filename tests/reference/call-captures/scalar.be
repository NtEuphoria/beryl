module reference.call_capture.scalar
struct R { x: i32 }
struct P { child: R }
fn scalar(value: i32, tag: i32) -> i32 { return value + tag }
fn replace(inout p: P) -> i32 { p = P{child: R{x: 9}}
    return 7 }
test "scalar let captures its value before later mutation" {
    var p = P{child: R{x: 1}}
    let got = scalar(p.child.x, replace(inout p))
    assert(got == 8)
    assert(p.child.x == 9)
    assert(got != 16)
    println(got)
}
