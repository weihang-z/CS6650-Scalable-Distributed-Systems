package main

import (
	"fmt"
	"sync"
)

func main() {
	m := make(map[int]int)

	var wg sync.WaitGroup

	for g := 0; g < 50; g++ {
		wg.Add(1)

		go func(g int) {
			for i := 0; i < 1000; i++ {
				m[g*1000 + i] = i
			}
			wg.Done()
		}(g)
	}

	wg.Wait()
	fmt.Println("len(m) =", len(m))
}
