module reference.expected_division_overflow
fn input(let n: i32) -> i32 { return n }
test "minimum divided by negative one" {
    let minimum = input(-2147483648)
    let negative_one = input(-1)
    println(minimum / negative_one)
}
