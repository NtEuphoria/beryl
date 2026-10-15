//! Fixed 64x64 i32 kernel. Bounds checks on `a[i][j]` are the Phase 4 target.

module bench.array_sum_2d

fn kernel() -> i32 {
    var a: [[i32; 64]; 64]
    for i in 0..64 {
        for j in 0..64 {
            a[i][j] = i + j
        }
    }
    var s: i32 = 0
    for k in 0..8000 {
        s = 0
        for i in 0..64 {
            for j in 0..64 {
                s += a[i][j]
            }
        }
    }
    return s
}

fn main() {
    println(kernel())
}
