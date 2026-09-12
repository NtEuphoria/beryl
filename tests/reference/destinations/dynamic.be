module reference.destination.dynamic
fn bump(inout x: i32) -> i32 { x += 1
    return x }
test "unknown index overlap" {
    var xs = [1, 2]
    let i = 0
    let j = 1
    xs[i] = bump(inout xs[j])
}
