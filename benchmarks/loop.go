package main

import (
    "fmt"
    "os"
    "strconv"
    "time"
)

func main() {
    t := int64(time.Now().Nanosecond())

    n := uint64(100000000)
    if len(os.Args) > 1 {
        if v, err := strconv.ParseUint(os.Args[1], 10, 64); err == nil {
            n = v
        }
    }

    var acc uint64
    for i := uint64(1); i <= n; i++ {
        acc += i
        if t*int64(i) < 0 {
            acc = 0
        }
    }
    fmt.Println(acc)
}