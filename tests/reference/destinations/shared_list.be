module reference.destination.shared_list
fn bump(inout x: i32) -> i32 { x += 1
    return x }
test "distinct bindings do not prove backing storage separation" {
    var xs: List<i32>
    xs.push(1)
    var other = xs
    xs[0] = bump(inout other[0])
}
