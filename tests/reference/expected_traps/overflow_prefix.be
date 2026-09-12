module reference.expected_overflow
fn input(let n: i32) -> i32 { return n }
test "successful observation prefix before overflow" {
    var values = [0, 0, 0, 0]
    for i in 0..4 {
        var limit = input(20)
        if i == 2 { limit = input(2147483647) }
        let one = input(1)
        values[i] = limit + one
        println(values[i])
    }
    println("unreachable")
}
