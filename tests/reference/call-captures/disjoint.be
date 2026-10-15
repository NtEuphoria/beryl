module reference.call_capture.disjoint
struct R { x: i32 }
struct P { child: R, other: R }
fn observe(let r: R, tag: i32) -> i32 { return r.x }
fn bump(inout value: i32) -> i32 { value += 1
    return value }
test "plain disjoint fields indices and index side effect stay admitted" {
    var p = P{child: R{x: 1}, other: R{x: 3}}
    let field_got = observe(p.child, bump(inout p.other.x))
    assert(field_got == 1)
    assert(p.child.x == 1)
    assert(p.other.x == 4)
    var xs = [R{x: 11}, R{x: 22}]
    let index_got = observe(xs[0], bump(inout xs[1].x))
    assert(index_got == 11)
    assert(xs[0].x == 11)
    assert(xs[1].x == 23)
    var index = -1
    let once_got = observe(xs[bump(inout index)], 0)
    assert(index == 0)
    assert(once_got == 11)
    println(field_got)
    println(index_got)
    println(once_got)
}
