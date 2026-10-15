#[derive(Clone, Copy)]
struct Blob {
    a: [i32; 32],
}

fn checksum(b: Blob) -> i32 {
    let mut s = 0i32;
    for i in 0..32 {
        s += b.a[i];
    }
    s
}

fn layer(b: Blob) -> i32 {
    checksum(b) + checksum(b)
}

fn main() {
    let mut b = Blob { a: [0; 32] };
    for i in 0..32 {
        b.a[i] = i as i32;
    }
    let mut s = 0i32;
    for _ in 0..100_000 {
        s = layer(b);
    }
    println!("{s}");
}
