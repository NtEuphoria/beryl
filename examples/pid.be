//! A small PID example. The complete MESH controller port is tracked in M3.

module flight.pid

pub struct Pid {
    kp: f32
    ki: f32 = 0
    kd: f32 = 0
    limit: f32 = 1
    integral: f32 = 0
    last_meas: f32 = 0
    has_last: bool = false
}

pub fn Pid.step(inout self, sp: f32, meas: f32, dt: f32) -> f32 {
    if dt <= 0 {
        return 0
    }
    let err = sp - meas
    self.integral = clamp(self.integral + err * dt, -self.limit, self.limit)
    var deriv: f32 = 0
    if self.has_last {
        deriv = -(meas - self.last_meas) / dt
    }
    self.last_meas = meas
    self.has_last = true
    return self.kp * err + self.ki * self.integral + self.kd * deriv
}
