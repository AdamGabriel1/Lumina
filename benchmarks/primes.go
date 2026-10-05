package main

import (
    "fmt"
    "os"
    "strconv"
)

func main() {
    limit := 10000000
    if len(os.Args) > 1 {
        if v, err := strconv.Atoi(os.Args[1]); err == nil {
            limit = v
        }
    }

    primes := make([]byte, limit)
    for i := range primes {
        primes[i] = 1
    }
    if limit > 0 { primes[0] = 0 }
    if limit > 1 { primes[1] = 0 }

    for p := 2; p*p < limit; p++ {
        if primes[p] == 1 {
            for i := p * p; i < limit; i += p {
                primes[i] = 0
            }
        }
    }

    count := 0
    for i := 0; i < limit; i++ {
        if primes[i] == 1 {
            count++
        }
    }
    fmt.Println(count)
}