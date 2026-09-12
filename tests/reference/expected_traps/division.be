module reference.expected_division
fn input(let n: i32) -> i32 { return n }
test "integer division by zero" {
    print("prefix:")
    let numerator = input(8)
    let denominator = input(0)
    println(numerator / denominator)
    println("unreachable")
}
