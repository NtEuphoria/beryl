module context.left

/// A plain value used by the compiler context regression.
pub struct State {
    /// Current controller value.
    value: f32 = 0f32
}

/// Replace the current value.
pub fn State.replace(inout self, value: f32 = 1f32) {
    self.value = value
}

pub fn shared(value: i32) -> i32 {
    return value
}

fn private_value() -> i32 {
    return 7
}
