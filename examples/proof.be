//! Exercises the lowerings the Enfusion backend has to get right.

module beryl.proof

pub struct Vec2i {
    x: i32 = 0
    y: i32 = 0
}

pub fn Vec2i.manhattan(let self) -> i32 {
    return abs(self.x) + abs(self.y)
}

pub struct Pid {
    kp: f32
    ki: f32 = 0
    limit: f32 = 1
    integral: f32 = 0
}

pub fn Pid.step(inout self, sp: f32, meas: f32, dt: f32) -> f32 {
    if dt <= 0 {
        return 0
    }
    let err = sp - meas
    self.integral = clamp(self.integral + err * dt, -self.limit, self.limit)
    return self.kp * err + self.ki * self.integral
}

pub struct Store {
    ids: List<i32>
    total: i32 = 0
}

pub fn Store.count(inout self, by: i32) {
    self.total += by
}

pub enum Mode {
    Idle
    Armed = 3
    Active
}

pub fn scale(let v: Vec2i, let by: i32) -> Vec2i {
    var out = v
    out.x = out.x * by
    out.y = out.y * by
    return out
}

pub fn swap_pair(inout a: i32, inout b: i32) {
    let t = a
    a = b
    b = t
}
