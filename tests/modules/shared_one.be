module shared
pub fn value() -> i32 { return hidden() }
test "same" { assert(value() == 2) }
