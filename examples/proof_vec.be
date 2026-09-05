module proof_vec

//! Every vector construct the enfusion back end can emit, in one file, so the
//! Workbench proof covers the whole surface rather than a sample.
//!
//! Vec2 and Vec4 are deliberately absent: EnforceScript's `vector` is exactly
//! three floats, so both are rejected at BE0701 before reaching here.

struct Rotor {
    offset: Vec3
    spin: f32
}

fn Rotor.thrust(let self, let demand: f32) -> Vec3 {
    return self.offset * (demand * self.spin)
}

fn mix(let a: Vec3, let b: Vec3, let t: f32) -> Vec3 {
    return a * (1.0 - t) + b * t
}

fn components(let v: Vec3) -> f32 {
    return v.x + v.y + v.z + v[0] + v[1] + v[2]
}

fn arithmetic(let a: Vec3, let b: Vec3, let s: f32) -> Vec3 {
    let sum = a + b
    let dif = a - b
    let cwm = a * b
    let cwd = a / b
    let up  = a * s
    let up2 = s * a
    let dn  = a / s
    return sum + dif + cwm + cwd + up + up2 + dn + (-a)
}

fn magnitudes(let a: Vec3, let b: Vec3) -> f32 {
    return a.length() + a.length_sq() + a.dot(b) + a.distance(b)
}

fn shapes(let a: Vec3, let b: Vec3) -> Vec3 {
    return a.normalized() + a.cross(b) + Vec3(1.0, 0.0, 0.0)
}

fn identical(let a: Vec3, let b: Vec3) -> bool {
    return a == b
}

fn differs(let a: Vec3, let b: Vec3) -> bool {
    return a != b
}

fn place(set out: Vec3) -> void {
    out = Vec3(0.0, 0.0, 0.0)
    out.y = 1.0
    out[2] = 2.0
}

fn loop_sum(let vs: Vec3) -> f32 {
    var total = 0.0f32
    var i = 0
    while i < 3 {
        total = total + vs[i]
        i += 1
    }
    return total
}
