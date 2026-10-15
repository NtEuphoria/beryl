module receiver_mode_order

struct R { x: i32 }
fn R.read(let self) -> i32 { return self.x }
fn R.take(sink self, tag: i32 = mark(5)) -> i32 { return self.x + tag }
fn R.fill(set self, value: i32 = mark(7)) { self = R{x: value} }
fn fill(set r: R, value: i32 = mark(7)) { r = R{x: value} }
fn mark(value: i32) -> i32 { println(value)
    return value }
fn index(sink n: i32) -> i32 { println(90)
    return n }

fn main() {
    var r: R
    r.fill()
    println(r.read())
    println(r.take())
    r.fill(11)
    println(r.read())
    var explicit: R
    fill(set explicit)
    println(explicit.read())
    let initialized_once: R
    initialized_once.fill(13)
    println(initialized_once.read())
    var xs = [R{x: 17}, R{x: 19}]
    var let_index = 0
    println(xs[index(sink let_index)].read())
    var set_index = 1
    xs[index(sink set_index)].fill(23)
    println(xs[1].x)
    println(R{x: 29}.take(2))
}
