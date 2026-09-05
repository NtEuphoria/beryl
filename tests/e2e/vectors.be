module vectors

// Every vector operation, on all three arities, with values chosen so a wrong
// answer is a different number rather than a coincidence.

fn main() -> void {
    let a = Vec3(1.0, 2.0, 3.0)
    let b = Vec3(4.0, 5.0, 6.0)

    // components, both spellings
    println(a.x)
    println(a.y)
    println(a.z)
    println(a[0])
    println(a[2])

    // component-wise arithmetic
    println((a + b).y)
    println((b - a).z)
    println((a * b).z)
    println((b / a).y)
    println((-a).x)

    // scaling, on either side
    println((a * 2.0).x)
    println((2.0 * a).y)
    println((a / 2.0).z)

    // products and magnitudes
    println(a.dot(b))
    println(a.length_sq())
    println(Vec3(3.0, 4.0, 0.0).length())
    println(Vec3(0.0, 0.0, 0.0).length())
    println(a.distance(b) > 5.19)
    println(a.distance(b) < 5.20)

    // cross: a x b, right-handed
    let c = a.cross(b)
    println(c.x)
    println(c.y)
    println(c.z)

    // normalized, including the zero case that must not be NaN
    println(Vec3(3.0, 4.0, 0.0).normalized().x)
    println(Vec3(3.0, 4.0, 0.0).normalized().y)
    println(Vec3(0.0, 0.0, 0.0).normalized().x)

    // equality is component-wise
    println(a == b)
    println(a == Vec3(1.0, 2.0, 3.0))

    // mutation through both spellings
    var m = Vec3(0.0, 0.0, 0.0)
    m.y = 7.0
    m[2] = 9.0
    println(m.x)
    println(m.y)
    println(m.z)

    // Vec2 and Vec4 exist natively even though the enfusion target rejects them
    let p = Vec2(3.0, 4.0)
    println(p.length())
    println(p.dot(Vec2(1.0, 1.0)))

    let q = Vec4(1.0, 2.0, 3.0, 4.0)
    println(q.w)
    println(q.length_sq())
}
