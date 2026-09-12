module context.right

pub struct State {
    value: i32
}

pub fn shared(value: i32) -> i32 {
    return value + 1
}
