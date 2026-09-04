module e2e.arith

fn main() {
    // precedence
    println(2 + 3 * 4)
    println((2 + 3) * 4)
    println(10 - 3 - 2)
    println(2 + 3 < 6 && 1 < 2)

    // integer division truncates toward zero
    println(7 / 2)
    println(-7 / 2)
    println(7 % 3)

    // bitwise and shifts
    println(6 & 3)
    println(6 | 3)
    println(6 ^ 3)
    println(1 << 4)
    println(256 >> 4)

    // unary
    println(-5)
    println(!false)
    println(~0i32)

    // floats keep their own arithmetic
    let a: f64 = 1.5
    let b: f64 = 0.25
    println(a + b)
    println(a * 4.0)
    println(sqrt(16.0))

    // explicit casts, because nothing is implicit
    let n: i32 = 300
    println(n as u8)
    println(n as i64 * 2)
    println(3.9 as i32)

    // width-specific types
    let big: i64 = 9000000000
    println(big)
    let small: u8 = 200
    println(small)

    // intrinsics
    println(min(3, 9))
    println(max(3, 9))
    println(clamp(15, 0, 10))
    println(abs(-42))
}
