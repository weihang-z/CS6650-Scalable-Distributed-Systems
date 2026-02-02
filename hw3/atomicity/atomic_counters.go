package main

import (
    "fmt"
    "sync"
)

func main() {

    ops := 1

    var wg sync.WaitGroup

    for range 50 {
        wg.Go(func() {
            for range 1000 {

                ops++
            }
        })
    }

    wg.Wait()

    fmt.Println("ops:", ops)
}