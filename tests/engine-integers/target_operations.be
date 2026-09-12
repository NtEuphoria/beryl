module engine.target_order

pub struct TargetOps { unused: i32 = 0 }
struct Counter { value: f32 = 0f32 }
fn Counter.next(inout self) -> f32 {
    self.value = 1f32
    return 9f32
}

// Vec3 is outside the bounded AST reference. This fixture has an independent
// expected result and runs only in native and engine execution.
pub fn TargetOps.vector_capture() -> i32 {
    var c = Counter{}
    let value = Vec3(c.value, c.next() + 0f32, c.value)
    return (value.x * 1000f32 + value.y * 100f32 + value.z * 10f32 + c.value) as i32
}
