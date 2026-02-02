package main

import (
	"fmt"
	"sync"
	"time"
)

func main() {
	start := time.Now()

	var m sync.Map 
	var wg sync.WaitGroup

	for g := 0; g < 50; g++ {
		wg.Add(1)

		go func(g int) {
			defer wg.Done()
			for i := 0; i < 1000; i++ {
				m.Store(g*1000+i, i)
			}
		}(g)
	}

	wg.Wait()
	fmt.Println("total time =", time.Since(start))

	count := 0
	m.Range(func(_, _ any) bool {
		count++
		return true
	})
	fmt.Println("len(m) =", count)
}
