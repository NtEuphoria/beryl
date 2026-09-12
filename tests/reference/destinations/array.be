module reference.destination.array
fn replace(inout xs: [i32; 2]) -> i32 { xs = [10, 20]
    return 7 }
test "array ancestor replacement" {
    var xs = [1, 2]
    xs[0] = replace(inout xs)
}
