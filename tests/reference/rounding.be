module reference.rounding
const FOLDED: f32 = 9223373686122217471
pub fn exercise() -> bool {
    let integer: f32 = 9223373686122217471
    let explicit = 9223373686122217471f32
    let expected: f32 = 9223373136366403584
    // Slightly above the midpoint between 1 and the next binary32 value.
    let decimal: f32 = 1.0000000596046447753906250000000001
    let next: f32 = 1.00000011920928955078125
    return integer == expected && explicit == expected && FOLDED == expected && decimal == next
}
test "binary32 literals round directly to their declared width" {
    assert(exercise())
}
