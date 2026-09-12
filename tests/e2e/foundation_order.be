module foundation.order

struct P { x: i32 }

fn mark(let x: i32) -> i32 {
    println(x)
    return x
}

fn value(let p: P = P{ x: mark(7) }) -> i32 {
    return p.x
}

fn pair(let x: i32, let y: i32) -> i32 {
    return x * 10 + y
}

fn optional(let x: i32) -> !i32 {
    println(x)
    return x
}

fn index(inout count: i32) -> i32 {
    count += 1
    return 0
}

fn exercise() {
    println(value() + value())
    println(pair(mark(1), mark(2)))
    println(false && ((optional(90) orelse 0) > 0))
    println(true || ((optional(91) orelse 0) > 0))
    var count = 0
    var items = [10]
    items[index(inout count)] += 5
    println(items[0])
    println(count)
}

fn main() { exercise() }
