fn kernel() -> i32 {
    let mut a = [[0i32; 64]; 64];
    for i in 0..64 {
        for j in 0..64 {
            a[i][j] = i as i32 + j as i32;
        }
    }
    let mut s = 0i32;
    for _ in 0..8000 {
        s = 0;
        for i in 0..64 {
            for j in 0..64 {
                s += a[i][j];
            }
        }
    }
    s
}

fn main() {
    println!("{}", kernel());
}
