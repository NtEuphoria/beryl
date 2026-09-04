module e2e.structs

struct Point {
    x: f64
    y: f64 = 0
}

struct Counter {
    n: i32 = 0
    step: i32 = 1
}

fn Counter.bump(inout self) {
    self.n += self.step
}

fn Counter.value(let self) -> i32 {
    return self.n
}

fn Point.len2(let self) -> f64 {
    return self.x * self.x + self.y * self.y
}

// `sink` consumes its argument; the caller's binding is dead afterwards.
fn consume(sink p: Point) -> f64 {
    return p.x
}

// `set` must be initialized on every path before returning.
fn split(let n: i32, set lo: i32, set hi: i32) {
    lo = n / 2
    hi = n - lo
}

fn main() {
    // defaults fill in the fields a literal omits
    let p = Point{ x: 3 }
    println(p.x)
    println(p.y)
    println(p.len2())

    var c = Counter{ step: 5 }
    c.bump()
    c.bump()
    c.bump()
    println(c.value())

    // struct values copy, so the original is untouched
    var d = c
    d.bump()
    println(c.value())
    println(d.value())

    let owned = Point{ x: 7, y: 1 }
    println(consume(sink owned))

    var lo: i32
    var hi: i32
    split(9, set lo, set hi)
    println(lo)
    println(hi)

    // arrays are value types, indexed with bounds checks
    let arr = [10, 20, 30, 40]
    println(arr[0])
    println(arr[3])
    var total = 0
    for v in arr {
        total += v
    }
    println(total)
}
