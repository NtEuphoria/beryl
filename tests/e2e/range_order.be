module range_order

fn upper(inout start: i32) -> i32 {
    start = 100
    println(7)
    return 3
}

fn main() {
    var start = 0
    var count = 0
    for i in start..upper(inout start) {
        count += 1
        println(i)
    }
    println(count)
    println(start)

    var stop = 3
    for i in 0..stop {
        println(i)
        stop = 0
    }
    var values: List<i32>
    values.push(1)
    values.push(2)
    for i in 0..values.len() {
        values.push(i)
    }
    println(values.len())
}
