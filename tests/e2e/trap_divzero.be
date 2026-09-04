module e2e.trap_divzero

fn main() {
    var d = 3
    var i = 0
    while i < 4 {
        println(12 / d)
        d -= 1
        i += 1
    }
}
