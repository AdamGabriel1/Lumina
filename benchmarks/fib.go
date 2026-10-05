package main

import (
    "fmt"
    "os"
    "strconv"
)

func fib(n int64) int64 {
    if n <= 1 {
        return n
    }
    return fib(n-1) + fib(n-2)
}

func main() {
    n := int64(35)
    if len(os.Args) > 1 {
        if v, err := strconv.ParseInt(os.Args[1], 10, 64); err == nil {
            n = v
        }
    }
    fmt.Println(fib(n))
}