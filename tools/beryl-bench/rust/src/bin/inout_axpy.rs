fn add(y: &mut [i32; 256], x: &mut [i32; 256]) {
    for i in 0..256 {
        y[i] = y[i] + x[i];
    }
}

fn main() {
    let mut x = [1i32; 256];
    let mut y = [0i32; 256];
    for _ in 0..20_000 {
        add(&mut y, &mut x);
    }
    let mut s = 0i32;
    for v in y {
        s += v;
    }
    println!("{s}");
}
