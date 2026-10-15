module reference.call_capture.snapshot
struct R { x: i32 }
struct P { child: R }
fn observe(let r: R, tag: i32) -> i32 { return r.x }
fn first(let xs: [i32; 2], tag: i32) -> i32 { return xs[0] }
fn replace(inout p: P) -> i32 { p = P{child: R{x: 9}}
    return 0 }
fn replace_array(inout xs: [i32; 2]) -> i32 { xs = [9, 8]
    return 0 }
test "explicit record and array snapshots preserve prior values" {
    var p = P{child: R{x: 1}}
    let snapshot = p.child
    let got = observe(snapshot, replace(inout p))
    assert(got == 1)
    assert(p.child.x == 9)
    assert(snapshot.x == 1)
    var xs = [1, 2]
    let array_snapshot = xs
    let array_got = first(array_snapshot, replace_array(inout xs))
    assert(array_got == 1)
    assert(xs[0] == 9)
    assert(array_snapshot[0] == 1)
    println(got)
    println(array_got)
}
