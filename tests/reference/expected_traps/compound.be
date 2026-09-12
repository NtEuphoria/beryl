module reference.expected_compound
fn rhs() -> i32 {
    println("rhs")
    return 1
}
test "compound assignment failure follows rhs observations" {
    var value = 2147483647
    value += rhs()
    println(value)
}
