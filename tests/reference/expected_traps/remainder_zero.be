module reference.expected_remainder_zero
fn input(let n: i32) -> i32 { return n }
test "remainder by zero is a source trap" {
    let value = input(7)
    let zero = input(0)
    println(value % zero)
}
