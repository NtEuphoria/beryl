module reference.destination.skipped
struct R { x: i32 }
fn change(inout r: R) -> bool { r = R{x: 10}
    return true }
fn number(value: bool) -> i32 { if value { return 1 }
    return 0 }
test "conservative skipped operand" {
    var r = R{x: 1}
    r.x = number(false && change(inout r))
}
