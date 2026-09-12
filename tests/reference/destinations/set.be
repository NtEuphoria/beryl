module reference.destination.out_value
struct R { x: i32 }
fn replace(set r: R) -> i32 { r = R{x: 10}
    return 7 }
test "set replacement" {
    var r = R{x: 1}
    r.x = replace(set r)
}
