package main

import (
	"fmt"
	"sync"
	"time"
)

func main() {
	start := time.Now()

	m := make(map[int]int)
	mu := sync.RWMutex{}

	var wg sync.WaitGroup

	for g := 0; g < 50; g++ {
		wg.Add(1)

		go func(g int) {
			for i := 0; i < 1000; i++ {
				mu.Lock()
				m[g*1000 + i] = i
				mu.Unlock()
			}
			wg.Done()
		}(g)
	}

	wg.Wait()
	fmt.Println("total time =", time.Since(start))
	fmt.Println("len(m) =", len(m))
}
