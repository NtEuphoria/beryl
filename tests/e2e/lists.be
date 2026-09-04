module e2e.lists

struct Store {
    ids: List<i32>
    label: str = "store"
}

fn Store.total(let self) -> i32 {
    var sum = 0
    for i in 0..self.ids.len() {
        sum += self.ids.get(i)
    }
    return sum
}

fn main() {
    var s = Store{ }
    println(s.ids.len())

    s.ids.push(10)
    s.ids.push(20)
    s.ids.push(30)
    println(s.ids.len())
    println(s.ids.get(0))
    println(s.ids.get(2))
    println(s.total())

    s.ids.set(1, 99)
    println(s.ids.get(1))
    println(s.total())

    // Growth past the initial capacity.
    var big: List<i32>
    for i in 0..100 {
        big.push(i)
    }
    println(big.len())
    println(big.get(99))

    s.ids.clear()
    println(s.ids.len())
    println(s.label)
}
