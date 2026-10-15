module reference.call_capture.direct_sink
struct R { x: i32 }
struct P { child: R }
fn observe(let r: R, sink p: P) -> i32 { return r.x }
test "direct later transfer cannot consume a captured parent" {
    var p = P{child: R{x: 1}}
    assert(observe(p.child, sink p) == 1)
}
