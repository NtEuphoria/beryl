module probe

// R19: an integer literal that does not fit its type
fn r19() -> i8 {
    let x: i8 = 300
    return x
}

// R13: constant division at the signed minimum
const R13A: i32 = -2147483648 / -1
const R13B: i32 = -2147483648 % -1

// R18: `catch` on something that is not an error union
fn r18() -> i32 {
    let a = 5 catch |e| { 0 }
    return a
}

// R11: `try` returns early, skipping the `set` obligation
fn helper() -> !i32 {
    return 1
}
fn r11(set slot: i32) -> !i32 {
    let a = try helper()
    slot = a
    return a
}

// R14: an error literal returned from a plain function
fn r14() -> i32 {
    return error.Nope
}
