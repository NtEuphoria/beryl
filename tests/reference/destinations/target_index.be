module reference.destination.target_index
struct R { xs: [i32; 2] }
fn replace(inout r: R) -> i32 { r = R{xs: [10, 20]}
    return 0 }
test "destination index mutates ancestor" {
    var r = R{xs: [1, 2]}
    r.xs[replace(inout r)] = 7
}
