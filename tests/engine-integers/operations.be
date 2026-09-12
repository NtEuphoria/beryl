module engine.integers

pub struct Ops { unused: i32 = 0 }

pub fn Ops.minimum(a: i32, b: i32) -> i32 { return min(a, b) }
pub fn Ops.maximum(a: i32, b: i32) -> i32 { return max(a, b) }
pub fn Ops.bounded(a: i32, lo: i32, hi: i32) -> i32 { return clamp(a, lo, hi) }
pub fn Ops.add(a: i32, b: i32) -> i32 { return saturating_add(a, b) }
pub fn Ops.subtract(a: i32, b: i32) -> i32 { return saturating_sub(a, b) }
pub fn Ops.minimum_float(a: f32, b: f32) -> f32 { return min(a, b) }
pub fn Ops.maximum_float(a: f32, b: f32) -> f32 { return max(a, b) }
pub fn Ops.bounded_float(a: f32, lo: f32, hi: f32) -> f32 { return clamp(a, lo, hi) }

struct Counter { value: i32 = 0 }
fn Counter.next(inout self) -> i32 {
    self.value += 1
    return self.value
}

pub fn Ops.order() -> i32 {
    var c = Counter{}
    let result = saturating_sub(c.next(), c.next())
    return c.value * 100 + result
}

pub fn Ops.clamp_order() -> i32 {
    var c = Counter{}
    let result = clamp(c.next(), c.next(), c.next())
    return c.value * 100 + result
}

pub fn Ops.capture() -> i32 {
    var c = Counter{}
    let result = min(c.value, c.next())
    return c.value * 100 + result
}

pub fn Ops.short_circuit() -> i32 {
    var c = Counter{}
    let unused = false && saturating_add(c.next(), c.next()) == 3
    return c.value
}

fn next_value(inout value: i32) -> i32 {
    value += 1
    return value
}

pub fn Ops.compound_order() -> i32 {
    var value = 4
    value += next_value(inout value)
    return value
}

fn upper_bound(inout start: i32) -> i32 {
    start = 100
    return 3
}

pub fn Ops.range_order() -> i32 {
    var start = 0
    var count = 0
    for i in start..upper_bound(inout start) {
        count += 1
    }
    return count * 1000 + start
}

pub fn Ops.range_once() -> i32 {
    var stop = 3
    var count = 0
    for i in 0..stop {
        count += 1
        stop = 0
    }
    return count
}

struct Pair { left: i32, right: i32 }

pub fn Ops.record_order() -> i32 {
    var c = Counter{}
    let pair = Pair{ right: c.next(), left: c.next() }
    return c.value * 100 + pair.left * 10 + pair.right
}

pub fn Ops.record_capture() -> i32 {
    var c = Counter{}
    let pair = Pair{ right: c.value, left: c.next() }
    return c.value * 100 + pair.left * 10 + pair.right
}

pub fn Ops.array_capture() -> i32 {
    var c = Counter{}
    let values = [c.value, c.next(), c.value]
    return c.value * 1000 + values[0] * 100 + values[1] * 10 + values[2]
}
