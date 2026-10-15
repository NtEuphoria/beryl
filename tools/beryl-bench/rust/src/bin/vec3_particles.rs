struct Vec3 {
    x: f32,
    y: f32,
    z: f32,
}

fn main() {
    let mut acc = 0i32;
    for _ in 0..4000 {
        let mut p = Vec3 { x: 1.0, y: 2.0, z: 3.0 };
        let v = Vec3 { x: 1.0, y: 0.5, z: 0.25 };
        for _ in 0..250 {
            p.x += v.x;
            p.y += v.y;
            p.z += v.z;
        }
        acc += p.x as i32;
    }
    println!("{acc}");
}
