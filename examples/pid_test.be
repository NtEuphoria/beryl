//! The PID controller, tested natively in milliseconds instead of a
//! 10-15 second Workbench build.

module flight.pid_tests
use flight.pid.Pid

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
