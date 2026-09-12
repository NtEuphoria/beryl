module reference.destination.nested
struct R { x: i32 }
struct Outer { r: R, other: i32 }
fn replace(inout r: R) -> i32 { r = R{x: 10}
    return 7 }
test "nested ancestor replacement" {
    var o = Outer{r: R{x: 1}, other: 0}
    o.r.x = replace(inout o.r)
}
