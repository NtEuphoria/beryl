fn main() {
    let mut xs: Vec<i32> = Vec::new();
    let mut last = 0i32;
    for _ in 0..2000 {
        for i in 0..256 {
            xs.push(i);
        }
        last = xs.len() as i32;
        xs.clear();
    }
    println!("{last}");
    println!("{}", xs.len());
}
