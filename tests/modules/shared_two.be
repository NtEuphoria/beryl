module shared
fn hidden() -> i32 { return 2 }
test "same" { assert(hidden() == 2) }
