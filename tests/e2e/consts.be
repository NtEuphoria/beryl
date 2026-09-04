module e2e.consts

const WIDTH: i32 = 4
const HEIGHT: i32 = 3
const CELLS: i32 = WIDTH * HEIGHT
const MASK: i32 = (1 << 5) - 1
const NAME: str = "beryl"
const ENABLED: bool = WIDTH > HEIGHT

fn main() {
    println(CELLS)
    println(MASK)
    println(NAME)
    println(ENABLED)

    // A constant is legal wherever an array length is required.
    let grid: [i32; CELLS] = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    println(grid[CELLS - 1])

    let shifted: [i32; 1 << 2] = [9, 8, 7, 6]
    println(shifted[0])
}
