module foundation.names

fn fails() -> !void { return error.Bad }
fn value() -> !i32 { return error.Bad }
fn announce() { println(42) }
fn forward() -> !void { return announce() }

fn exercise() {
    let x = 3
    {
        let x = x + 1
        println(x)
    }
    println(x)
    let int = 5
    let int_ = 6
    let _t0 = 7
    println(int + int_ + _t0)
    fails() catch |e| { println(e > 0) }
    println(value() catch |e| { println(e > 0) })
    forward() catch |e| { println(false) }
    defer announce()
}

fn main() { exercise() }
