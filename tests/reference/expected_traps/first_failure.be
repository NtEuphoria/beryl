module reference.expected_order
fn divide() -> i32 {
    println("first")
    let zero = 0
    return 1 / zero
}
fn multiply() -> i32 {
    println("second")
    let large = 2147483647
    return large * 2
}
fn combine(let first: i32, let second: i32) -> i32 { return first + second }
test "first source failure wins across arguments" {
    println(combine(divide(), multiply()))
}
