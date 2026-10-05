package main

import (
    "fmt"
    "os"
    "strconv"
)

func main() {
    n := 200
    if len(os.Args) > 1 {
        if v, err := strconv.Atoi(os.Args[1]); err == nil {
            n = v
        }
    }
    size := n * n

    a := make([]int64, size)
    b := make([]int64, size)
    c := make([]int64, size)

    for i := 0; i < size; i++ {
        a[i] = int64(i % 10)
        b[i] = int64((i * 2) % 10)
    }

    for i := 0; i < n; i++ {
        for j := 0; j < n; j++ {
            var s int64
            for k := 0; k < n; k++ {
                s += a[i*n+k] * b[k*n+j]
            }
            c[i*n+j] = s
        }
    }

    var total int64
    for _, v := range c {
        total += v
    }
    fmt.Println(total)
}