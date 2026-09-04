module hello

fn main() {
    println("Hello from Beryl")
    var sum = 0
    for i in 1..11 {
        sum += i
    }
    print("sum 1..10 = ")
    println(sum)
}
