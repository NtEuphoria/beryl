module intrinsic_order

struct IntCounter { value: i32 }
fn IntCounter.next(inout self) -> i32 {
    self.value = 1
    return 9
}
struct FloatCounter { value: f32 }
fn FloatCounter.next(inout self) -> f32 {
    self.value = 1f32
    return 9f32
}
struct VectorCounter { value: Vec3 }
fn VectorCounter.next(inout self) -> Vec3 {
    self.value = Vec3(9, 0, 0)
    return Vec3(2, 0, 0)
}

fn main() {
    var c = IntCounter{ value: 0 }
    var xs: List<i32>
    xs.push(0)
    xs.push(0)
    xs.set(c.value, c.next() + 0)
    println(xs[0])
    println(xs[1])
    println(c.value)
    var f = FloatCounter{ value: 0f32 }
    let value = Vec3(f.value, f.next() + 0f32, f.value)
    println(value.x)
    println(value.y)
    println(value.z)
    println(f.value)
    var v = VectorCounter{ value: Vec3(1, 0, 0) }
    println(v.value.dot(v.next()))
    println(v.value.x)
}
