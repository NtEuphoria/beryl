module reference.call_capture.nested_sink
struct R { x: i32 }
struct P { child: R }
fn observe(let r: R, tag: i32) -> i32 { return r.x }
fn consume(sink p: P) -> i32 { return p.child.x }
test "nested transfer cannot consume a captured parent" {
    var p = P{child: R{x: 1}}
    assert(observe(p.child, consume(sink p)) == 1)
}
