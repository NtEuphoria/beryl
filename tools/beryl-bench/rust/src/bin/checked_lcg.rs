fn main() {
    let mut x: i32 = 1;
    for _ in 0..20_000_000 {
        x = x + 2;
        x = x - 1;
    }
    println!("{x}");
}
