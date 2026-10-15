module reference.call_capture.projected_array
struct P { xs: [i32; 2] }
fn first(let xs: [i32; 2], tag: i32) -> i32 { return xs[0] }
fn replace(inout p: P) -> i32 { p = P{xs: [9, 8]}
    return 0 }
test "projected fixed array cannot survive parent replacement" {
    var p = P{xs: [1, 2]}
    assert(first(p.xs, replace(inout p)) == 1)
}
