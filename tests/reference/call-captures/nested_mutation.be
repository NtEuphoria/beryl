module reference.call_capture.nested_mutation
struct R { x: i32 }
struct P { child: R }
fn observe(let r: R, tag: i32) -> i32 { return r.x }
fn wrap(x: i32) -> i32 { return x }
fn replace(inout p: P) -> i32 { p = P{child: R{x: 9}}
    return 0 }
test "later nested calls cannot conceal parent replacement" {
    var p = P{child: R{x: 1}}
    assert(observe(p.child, wrap(wrap(replace(inout p)))) == 1)
}
