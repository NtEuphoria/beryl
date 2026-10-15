module reference.call_capture.defaults
struct R { x: i32 }
fn mark(value: i32) -> i32 { println(77)
    return value }
fn observe(let r: R, tag: i32 = mark(0)) -> i32 { return r.x + tag }
fn R.observe(let self, tag: i32 = mark(0)) -> i32 { return self.x + tag }
test "expanded nonmutating defaults execute once per free and method call" {
    let r = R{x: 1}
    let free_got = observe(r)
    let method_got = r.observe()
    assert(free_got == 1)
    assert(method_got == 1)
    println(free_got)
    println(method_got)
}
