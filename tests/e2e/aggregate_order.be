module aggregate_order

struct Pair { left: i32, right: i32 }
struct Counter { value: i32 = 0 }
fn Counter.next(inout self) -> i32 {
    self.value += 1
    return self.value
}
fn mark(value: i32) -> i32 {
    println(value)
    return value
}
struct Defaults { first: i32 = 4, second: i32 = 5 }

fn main() {
    let pair = Pair{ right: mark(2), left: mark(1) }
    println(pair.left * 10 + pair.right)
    var counter = Counter{}
    let captured = Pair{ right: counter.value, left: counter.next() }
    println(captured.left * 10 + captured.right)
    let array = [counter.value, counter.next(), counter.value]
    println(array[0] * 100 + array[1] * 10 + array[2])
    let defaults = Defaults{ second: mark(3) }
    println(defaults.first * 10 + defaults.second)
    let copied = defaults
    println(copied.first * 10 + copied.second)
}
