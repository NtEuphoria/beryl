//! f32 Vec3 integration. Phase 5 native profile flags (FMA, target-cpu) are
//! measured against this kernel. The printed checksum is a truncated x.

module bench.vec3_particles

fn main() {
    var acc: i32 = 0
    for k in 0..4000 {
        var p = Vec3(1.0, 2.0, 3.0)
        let v = Vec3(1.0, 0.5, 0.25)
        for i in 0..250 {
            p = p + v
        }
        acc += p.x as i32
    }
    println(acc)
}
