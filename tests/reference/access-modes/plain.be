module access_modes
struct R { x: i32, y: i32 }
fn fill(set r: R, n: i32 = 7) { r = R {x: n, y: n + 1} }
fn take(sink r: R) -> i32 { r.x += 1
return r.x + r.y }
fn R.fill(set self, n: i32 = 7) { self = R {x: n, y: n + 1} }
fn R.take(sink self, n: i32 = 0) -> i32 { self.x += n
return self.x + self.y }
fn mark(let n: i32) -> i32 { println(n)
return n }
fn scalar(set n: i32, v: i32) { n = v }
fn outer(set r: R) { fill(set r, 10) }
fn renew(set r: R) { fill(set r, 2)
let before = take(sink r)
assert(before == 6)
fill(set r, before) }
fn condition(set n: i32) -> bool { n = 14
return false }
fn consume(sink n: i32) -> i32 { return n }
fn choose(set n: i32, flag: bool) { if flag { n = 3
return }
n = 4 }
fn receiver_index(sink n: i32) -> i32 { println(90)
return n }
fn R.default_fill(set self, n: i32 = mark(7)) { self = R {x: n, y: 1} }
fn R.default_take(sink self, n: i32 = mark(5)) -> i32 { return self.x + n }
test "uninitialized and immutable set" {
 let r: R
fill(set r)
assert(r.x == 7)
assert(r.y == 8)
 var n: i32
n = 4
assert(n == 4)
 let m: i32
scalar(set m, 5)
assert(m == 5)
}
test "moves replace whole values without aliasing" {
 let original = R{x: 2, y: 3}
let copied = original
 assert(take(sink original) == 6)
fill(set original, 9)
 assert(original.x == 9)
assert(copied.x == 2)
 var values = [1, 2]
let snapshot = values
 assert(array_take(sink values) == 8)
array_fill(set values)
 assert(values[0] == 4)
assert(snapshot[0] == 1)
}
fn array_take(sink xs: [i32; 2]) -> i32 { xs[0] = 6
return xs[0] + xs[1] }
fn array_fill(set xs: [i32; 2]) { xs = [4, 5] }
test "receiver explicit defaults and captures" {
 var r: R
r.default_fill()
assert(r.default_take() == 12)
 r.fill(8)
assert(r.take(1) == 18)
 var a = [R{x: 1, y: 2}]
var i = 0
 a[receiver_index(sink i)].fill(23)
assert(a[0].x == 23)
 assert(R{x: 2, y: 4}.take() == 6)
}
test "nested set and set parameter move" {
 var r: R
outer(set r)
assert(r.x == 10)
 renew(set r)
assert(r.x == 6)
}
test "branch and loop states" {
 var n: i32
choose(set n, true)
assert(n == 3)
 choose(set n, false)
assert(n == 4)
 var r = R{x: 1,y: 2}
var sum = 0
 for i in 0..3 { let local = R{x: i, y: 2}
sum += take(sink local)
   let old = take(sink r)
fill(set r, i)
if i == 1 { continue }
assert(old > 0)
 }
 assert(sum == 12)
assert(r.x == 2)
 while condition(set n) { assert(false) }
assert(n == 14)
 for j in 0..2 { consume(sink n)
break }
scalar(set n, 19)
assert(n == 19)
}
test "immediate defer and initialization" {
 var n: i32
defer scalar(set n, 12)
assert(n == 12)
}
