//! Large `let` aggregate passed through a call chain. Phase 2 pointer-passing
//! should drop the per-call copies.

module bench.struct_pass

struct Blob {
    a: [i32; 32]
}

fn checksum(let b: Blob) -> i32 {
    var s: i32 = 0
    for i in 0..32 {
        s += b.a[i]
    }
    return s
}

fn layer(let b: Blob) -> i32 {
    return checksum(b) + checksum(b)
}

fn main() {
    var b = Blob{ a: [
        0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0
    ] }
    for i in 0..32 {
        b.a[i] = i
    }
    var s: i32 = 0
    for k in 0..100000 {
        s = layer(b)
    }
    println(s)
}
