module reference.expected_bounds
fn input(let n: i32) -> i32 { return n }
test "fixed array boundary" {
    let values = [10, 20]
    println(values[0])
    let index = input(2)
    println(values[index])
}
