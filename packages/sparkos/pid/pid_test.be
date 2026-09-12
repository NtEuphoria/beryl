//! Analytical answers use powers of two where exact binary32 results are intended.
module sparkos.flight.pid_tests
use sparkos.flight.pid.Pid

fn observe(let p: Pid, output: f32) {
    println(output)
    println(p.kp)
    println(p.ki)
    println(p.kd)
    println(p.integral_limit)
    println(p.integral)
    println(p.last_measurement)
    println(p.has_last)
    println(p.derivative_tau)
    println(p.derivative_filtered)
}

fn same(let a: Pid, let b: Pid) {
    assert(a.kp == b.kp && a.ki == b.ki && a.kd == b.kd)
    assert(a.integral_limit == b.integral_limit && a.integral == b.integral)
    assert(a.last_measurement == b.last_measurement && a.has_last == b.has_last)
    assert(a.derivative_tau == b.derivative_tau && a.derivative_filtered == b.derivative_filtered)
}

test "defaults constructor normalization and setter distinction" {
    var p = Pid.make()
    same(p, Pid{})
    assert(p.step(4, 1, 0.5) == 0)
    assert(p.get_integral() == 1)
    var negative = Pid.make(1, 2, 3, -1, -0.5)
    assert(negative.integral_limit == -1 && negative.derivative_tau == 0)
    assert(negative.step(0, 0, 0.5) == 2)
    assert(negative.integral == 1)
    negative.set_integral_limit(-1)
    assert(negative.integral_limit == 0)
    negative.set_derivative_tau(-2)
    assert(negative.derivative_tau == 0)
    observe(negative, 0)
}

test "proportional and integral independent analytical fixtures" {
    var p = Pid.make(2, 0, 0, 100)
    assert(p.step(4, 1, 0.5) == 6)
    assert(p.integral == 1.5 && p.last_measurement == 1 && p.has_last)
    p.set_gains(0, 2, 0)
    assert(p.step(4, 1, 0.5) == 6)
    assert(p.get_integral() == 3)
    observe(p, 6)
}

test "nonpositive timestep preserves every persistent field" {
    var p = Pid.make(1, 2, 3, 4, 0.25)
    let initial = p.step(2, 1, 0.25)
    let before = p
    assert(p.step(100, -100, 0) == 0)
    same(p, before)
    assert(p.step(100, -100, -0.5, true) == 0)
    same(p, before)
    observe(p, initial)
}

test "first measurement derivative and no setpoint kick" {
    var p = Pid.make(0, 0, 2)
    assert(p.step(10, 3, 0.5) == 0)
    assert(p.step(100, 3, 0.5) == 0)
    assert(p.step(100, 4, 0.5) == -4)
    assert(p.step(100, 3, 0.25) == 8)
    observe(p, 8)
}

test "clamp saturation freeze and release boundaries" {
    var p = Pid.make(0, 1, 1, 0.5)
    assert(p.step(10, 0, 1) == 0.5)
    let old = p.integral
    assert(p.step(-10, 1, 0.5, true) == -1.5)
    assert(p.integral == old)
    assert(p.last_measurement == 1)
    assert(p.step(-10, 1, 0.5, false) == -0.5)
    p.set_integral_limit(0)
    assert(p.integral == -0.5)
    let frozen = p.step(0, 1, 1, true)
    assert(p.integral == -0.5)
    let released = p.step(0, 1, 1)
    assert(p.integral == 0)
    observe(p, released)
}

test "derivative filter exact lag disable and reenable retain history" {
    var p = Pid.make(0, 0, 1, 1, 0.5)
    assert(p.step(0, 0, 0.5) == 0)
    assert(p.step(0, 1, 0.5) == -1)
    assert(p.derivative_filtered == -1)
    assert(p.step(0, 2, 0.5) == -1.5)
    p.set_derivative_tau(0)
    assert(p.step(0, 4, 0.5) == -4)
    assert(p.derivative_filtered == -1.5)
    p.set_derivative_tau(0.5)
    assert(p.step(0, 4, 0.5) == -0.75)
    observe(p, -0.75)
}

test "reset and handover preserve configuration clear dynamic state" {
    var p = Pid.make(1, 2, 3, 4, 0.5)
    let first = p.step(4, 1, 0.5)
    let second = p.step(4, 2, 0.5)
    p.reset()
    same(p, Pid.make(1, 2, 3, 4, 0.5))
    assert(p.step(4, 3, 0.5) == 2)
    assert(p.derivative_filtered == 0)
    p.set_gains(2, 0, 0)
    assert(p.integral == 0.5 && p.has_last)
    assert(p.step(4, 3, 0.5) == 2)
    observe(p, 2)
}

test "long seeded operations observe every transition" {
    var seed: i32 = 104729
    var p = Pid.make(0.5, 0.25, 0.125, 2, 0.0625)
    observe(p, 0)
    for i in 0..1024 {
        seed = wrapping_add(wrapping_mul(seed, 1664525), 1013904223)
        let sample = seed & 65535
        let measurement = (sample as f32 - 32768.0) / 8192.0
        let setpoint = ((seed >> 16) as f32) / 8192.0
        if i % 79 == 0 {
            p.reset()
            observe(p, 0)
        }
        if i % 43 == 0 {
            p.set_derivative_tau(0.0625)
            observe(p, 0)
        }
        if i % 47 == 0 {
            p.set_derivative_tau(-1)
            observe(p, 0)
        }
        if i % 97 == 0 {
            p.set_gains(0.5, 0.25, 0.125)
            observe(p, 0)
        }
        if i % 89 == 0 {
            p.set_integral_limit((i % 3) as f32)
            observe(p, 0)
        }
        var dt: f32 = 0.015625
        if i % 31 == 0 { dt = 0 }
        if i % 53 == 0 { dt = -0.015625 }
        let saturated = i % 7 == 0
        let old = p
        let output = p.step(setpoint, measurement, dt, saturated)
        if dt <= 0 {
            same(p, old)
        } else {
            assert(p.has_last && p.last_measurement == measurement)
            if saturated { assert(p.integral == old.integral) }
            else { assert(abs(p.integral) <= p.integral_limit) }
        }
        observe(p, output)
    }
}
