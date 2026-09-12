module foundation.numbers

const LOW: i64 = -9223372036854775808
const HIGH: u64 = 18446744073709551615u64
const ONE: f32 = 1.0
const REM: i64 = LOW % -1
const NARROW: i8 = 255 as i8

fn main() {
    println(-128i8)
    println(-32768i16)
    println(-2147483648)
    println(LOW)
    println(HIGH)
    println(HIGH > 1u64)
    println(ONE)
    println(REM)
    println(LOW % -1)
    println(NARROW)
    println(wrapping_mul(65535u16, 65535u16))
    println(wrapping_mul(-1i16, -1i16))
    println(-1 << 1)
    println(-2 >> 1)
}
