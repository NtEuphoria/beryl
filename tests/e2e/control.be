module e2e.control

fn fact(let n: i64) -> i64 {
    if n <= 1 {
        return 1
    }
    return n * fact(n - 1)
}

fn fib(let n: i32) -> i32 {
    if n < 2 {
        return n
    }
    return fib(n - 1) + fib(n - 2)
}

fn classify(let n: i32) -> i32 {
    if n < 0 {
        return -1
    } else if n == 0 {
        return 0
    } else {
        return 1
    }
}

fn main() {
    println(fact(10))
    println(fib(15))

    println(classify(-9))
    println(classify(0))
    println(classify(9))

    // while with break and continue
    var i = 0
    var evens = 0
    while true {
        i += 1
        if i > 20 {
            break
        }
        if i % 2 == 1 {
            continue
        }
        evens += i
    }
    println(evens)

    // ranges are half-open
    var count = 0
    for k in 0..5 {
        count += 1
    }
    println(count)

    // nested loops
    var grid = 0
    for r in 0..3 {
        for c in 0..4 {
            grid += 1
        }
    }
    println(grid)

    // deferred initialization proven by the ownership pass
    var pick: i32
    if evens > 100 {
        pick = 1
    } else {
        pick = 2
    }
    println(pick)

    // strings and chars
    println("done")
    print("char: ")
    println('A')
}
