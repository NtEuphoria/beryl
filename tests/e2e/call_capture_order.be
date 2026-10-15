module call_capture_order

struct R { x: i32, y: i32 }
struct P { child: R, other: R }
fn replace(inout p: P) -> i32 {
    p = P{child: R{x: 9, y: 8}, other: R{x: 7, y: 6}}
    return 0
}
fn bump(inout n: i32) -> i32 { n += 1
    return n
}
fn observe(let r: R, n: i32 = 0) -> i32 { return r.x }
fn scalar(n: i32, tag: i32) -> i32 { return n }

fn main() {
    var p = P{child: R{x: 1, y: 2}, other: R{x: 3, y: 4}}
    let snapshot = p.child
    println(observe(snapshot, replace(inout p)))
    println(p.child.x)
    println(scalar(p.child.x, replace(inout p)))
    println(observe(p.child, bump(inout p.other.x)))
    var xs = [snapshot, p.child]
    println(observe(xs[0], bump(inout xs[1].x)))
    println(xs[1].x)
    var index = -1
    println(observe(xs[bump(inout index)]))
    println(index)
}
