module collision.left
const BASE: i32 = 2
pub const SIZE: i32 = BASE + 1
pub struct P {
    out: i32
    out_: i32 = 1
    be_f_out: i32 = 2
}
pub fn P.get(let self) -> i32 { return self.out + self.out_ + self.be_f_out + SIZE }
pub fn P.make(let value: i32) -> P { return P{out: value} }
pub fn P.BerylCopy(let self) -> i32 { return self.out }
pub fn P.foo_bar(let self) -> i32 { return 11 }
pub fn P.FooBar(let self) -> i32 { return 12 }
pub fn size() -> i32 { return SIZE }
test "same" { assert(size() == 3) }
