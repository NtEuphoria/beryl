//! The PID controller, tested natively in milliseconds instead of a
//! 10-15 second Workbench build.

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

test "proportional term responds to error" {
    var p = Pid{ kp: 2 }
    let out = p.step(10, 4, 0.1)
    assert(out > 11.9)
    assert(out < 12.1)
}

test "a non-positive dt produces no output" {
    var p = Pid{ kp: 2 }
    assert(p.step(10, 0, 0) == 0)
}

test "the integral is clamped to the limit" {
    var p = Pid{ kp: 0, ki: 1, limit: 0.5 }
    for i in 0..100 {
        let ignored = p.step(10, 0, 0.1)
    }
    assert(p.integral <= 0.5)
}

test "derivative on measurement produces no setpoint kick" {
    var p = Pid{ kp: 0, kd: 1 }
    let first = p.step(0, 0, 0.1)
    let kick = p.step(100, 0, 0.1)
    assert(kick == 0)
}
