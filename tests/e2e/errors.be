module e2e.errors

// `!T` is an error union: a tag plus a value, no allocation and no unwinding.
fn parse_digit(let c: char) -> !i32 {
    if c < '0' {
        return error.NotADigit
    }
    if c > '9' {
        return error.NotADigit
    }
    return c as i32 - 48
}

// `try` propagates; it requires the caller to return `!T` too.
fn sum_two(let a: char, let b: char) -> !i32 {
    let x = try parse_digit(a)
    let y = try parse_digit(b)
    return x + y
}

fn main() {
    // orelse supplies a value when one is absent
    println(parse_digit('7') orelse -1)
    println(parse_digit('z') orelse -1)

    println(sum_two('3', '4') orelse -1)
    println(sum_two('3', 'z') orelse -1)

    // catch runs a handler; the binding is the error tag
    let v = parse_digit('x') catch |e| {
        println("handled")
    }
    println(v)

    println("end")
}
