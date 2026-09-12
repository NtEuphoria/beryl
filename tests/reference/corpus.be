module reference.corpus

struct P { n: i32 }
struct Q { values: [P; 2] }
fn P.mark(inout self) { self.n = 7 }
fn next(inout n: i32) -> i32 {
    n += 1
    return n
}
fn pack(let a: i32, let b: i32) -> i32 { return a * 10 + b }
fn yes(inout n: i32) -> bool {
    n += 1
    return true
}
fn side() -> i32 {
    print("side:")
    return 7
}
fn index(inout count: i32) -> i32 {
    count += 1
    return 0
}
fn take(sink value: P) -> i32 { return value.n }
fn fill(set n: i32) { n = 7 }
fn take_number(sink n: i32) -> i32 { return n + 1 }
fn bump(inout n: i32) { n += 1 }
fn early(let n: i32) -> i32 {
    if n > 0 { return 3 }
    return 4
}

test "finite numeric operations and bit observations" {
    let x: f32 = 16777216
    let one: f32 = 1
    assert((x + one) - x == 0)
    assert(x + (one - x) == 1)
    assert(wrapping_add(2147483647, 1) == -2147483648)
    assert(wrapping_mul(2147483647, 2) == -2)
    assert(saturating_sub(-2147483648, 1) == -2147483648)
    let a: f32 = 2.25
    assert(sqrt(a) == 1.5)
    let positive: f32 = 0
    let negative: f32 = -0.0
    print(positive)
    print(",")
    print(negative)
    print(",")
    println(0.1f32)
}
test "ordered evaluation and short circuit" {
    var n = 0
    assert(pack(next(inout n), next(inout n)) == 12)
    var x = 4
    x += next(inout x)
    assert(x == 9)
    let a = false && yes(inout n)
    let b = true || yes(inout n)
    assert(n == 2)
    println(side())
}
test "independent nested values indexed copy and whole-value sink" {
    var original = Q{values: [P{n: 1}, P{n: 2}]}
    var copy = original
    copy.values[0].mark()
    assert(original.values[0].n == 1)
    assert(copy.values[0].n == 7)
    copy = copy
    var calls = 0
    let element = copy.values[index(inout calls)]
    let n = take(sink element)
    assert(n == 7)
    assert(calls == 1)
}
test "access modes immediate defer and structured exits" {
    var n: i32
    fill(set n)
    assert(n == 7)
    let moved = take_number(sink n)
    assert(moved == 8)
    var x = 0
    defer bump(inout x)
    assert(x == 1)
    for i in 0..10 {
        if i == 2 { continue }
        if i == 5 { break }
        x += i
    }
    assert(x == 9)
    while x < 12 { x += 1 }
    assert(x == 12)
    assert(early(1) == 3)
}
