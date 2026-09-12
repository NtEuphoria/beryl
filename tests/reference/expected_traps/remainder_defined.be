module reference.remainder_defined
fn input(let n: i32) -> i32 { return n }
test "minimum remainder negative one is zero" {
    let minimum = input(-2147483648)
    let negative_one = input(-1)
    assert(minimum % negative_one == 0)
    println(minimum % negative_one)
}
