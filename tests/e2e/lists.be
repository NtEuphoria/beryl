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

    // `for v in list` — this emitted no loop at all until it was tested.
    var xs: List<i32>
    xs.push(10)
    xs.push(20)
    xs.push(30)
    var seen = 0
    for v in xs {
        seen += v
    }
    println(seen)

    // Bracket indexing on a list is not array indexing: the elements live
    // behind a pointer and the bound is a runtime field.
    println(xs[0])
    println(xs[2])
    xs[1] = 99
    println(xs[1])

    // An empty list iterates zero times rather than reading past the end.
    var empty: List<i32>
    var count = 0
    for v in empty {
        count += 1
    }
    println(count)

    // Strings compare by content; `==` on the slice struct is not equality.
    println(s.label == "store")
    println(s.label == "other")
    println(s.label != "other")
    println("" == "")
}
