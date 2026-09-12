module reference.expected_negation
fn input(let n: i32) -> i32 { return n }
test "minimum integer negation" {
    let minimum = input(-2147483648)
    println("negate")
    println(-minimum)
}
