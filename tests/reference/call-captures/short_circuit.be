module reference.call_capture.short_circuit
struct R { x: i32 }
struct P { child: R }
fn observe(let r: R, flag: bool) -> i32 { return r.x }
fn replace(inout p: P) -> bool { p = P{child: R{x: 9}}
    return true }
test "potential short circuit mutation remains conservatively rejected" {
    var p = P{child: R{x: 1}}
    assert(observe(p.child, false && replace(inout p)) == 1)
}
