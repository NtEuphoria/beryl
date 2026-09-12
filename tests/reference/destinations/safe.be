module reference.destination.safe
struct R { x: i32, y: i32 }
fn bump(inout x: i32) -> i32 { x += 1
    return x }
fn replace(inout r: R) -> i32 { r = R{x: 10, y: 20}
    return 7 }
test "disjoint projected places" {
    var r = R{x: 1, y: 2}
    r.x = bump(inout r.y)
    assert(r.x == 3)
    assert(r.y == 3)
    var xs = [1, 2]
    xs[0] = bump(inout xs[1])
    assert(xs[0] == 3)
    var index = -1
    xs[bump(inout index)] += 4
    assert(index == 0)
    assert(xs[0] == 7)
    let value = replace(inout r)
    r.x = value
    assert(r.x == 7)
    assert(r.y == 20)
    var x = 4
    x += bump(inout x)
    assert(x == 9)
}
