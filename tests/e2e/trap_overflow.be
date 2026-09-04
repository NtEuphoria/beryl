module e2e.trap_overflow

// Rust wraps silently here in release. Beryl traps in every build.
fn main() {
    var n: i32 = 2147483600
    var i = 0
    while i < 100 {
        n += 1
        i += 1
    }
    println(n)
}
