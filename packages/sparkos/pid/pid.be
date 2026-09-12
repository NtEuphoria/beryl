//! Complete SPK_PID behavior; source fixture and compatibility contract are in reference/.
//! Field and statement order deliberately follow the existing MESH controller.
module sparkos.flight.pid

pub struct Pid {
    kp: f32 = 0
    ki: f32 = 0
    kd: f32 = 0
    integral_limit: f32 = 1
    integral: f32 = 0
    last_measurement: f32 = 0
    has_last: bool = false
    derivative_tau: f32 = 0
    derivative_filtered: f32 = 0
}

//! Constructor initializer. Unlike set_integral_limit, retain a negative input limit.
pub fn Pid.initialize(inout self, kp: f32 = 0, ki: f32 = 0, kd: f32 = 0,
                      integral_limit: f32 = 1, derivative_tau: f32 = 0) {
    self.kp = kp
    self.ki = ki
    self.kd = kd
    self.integral_limit = integral_limit
    self.derivative_tau = max(0f32, derivative_tau)
    self.integral = 0
    self.last_measurement = 0
    self.has_last = false
    self.derivative_filtered = 0
}

pub fn Pid.make(kp: f32 = 0, ki: f32 = 0, kd: f32 = 0,
                integral_limit: f32 = 1, derivative_tau: f32 = 0) -> Pid {
    var pid = Pid{}
    pid.initialize(kp, ki, kd, integral_limit, derivative_tau)
    return pid
}

pub fn Pid.set_derivative_tau(inout self, tau: f32) {
    self.derivative_tau = max(0f32, tau)
}

pub fn Pid.set_gains(inout self, kp: f32, ki: f32, kd: f32) {
    self.kp = kp
    self.ki = ki
    self.kd = kd
}

pub fn Pid.set_integral_limit(inout self, limit: f32) {
    self.integral_limit = max(0f32, limit)
}

pub fn Pid.get_integral(let self) -> f32 { return self.integral }

pub fn Pid.reset(inout self) {
    self.integral = 0
    self.last_measurement = 0
    self.has_last = false
    self.derivative_filtered = 0
}

pub fn Pid.step(inout self, setpoint: f32, measurement: f32, dt: f32,
                saturated: bool = false) -> f32 {
    if dt <= 0 { return 0 }
    let err = setpoint - measurement
    if !saturated {
        self.integral += err * dt
        self.integral = clamp(self.integral, -self.integral_limit, self.integral_limit)
    }
    var derivative: f32 = 0
    if self.has_last {
        derivative = -(measurement - self.last_measurement) / dt
    }
    self.last_measurement = measurement
    self.has_last = true
    if self.derivative_tau > 0 {
        let alpha = dt / (self.derivative_tau + dt)
        self.derivative_filtered += alpha * (derivative - self.derivative_filtered)
        derivative = self.derivative_filtered
    }
    return (self.kp * err) + (self.ki * self.integral) + (self.kd * derivative)
}
