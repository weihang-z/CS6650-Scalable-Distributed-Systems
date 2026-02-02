package main

import (
	"fmt"
	"runtime"
	"time"
)

func pingPong(rounds int) (time.Duration, time.Duration) {
	ch := make(chan struct{})
	done := make(chan struct{})
	start := time.Now()

	go func() {
		for i := 0; i < rounds; i++ {
			ch <- struct{}{} 
			<-ch 
		}
		close(done)
	}()

	go func() {
		for i := 0; i < rounds; i++ {
			<-ch 
			ch <- struct{}{}
		}
	}()

	<-done
	total := time.Since(start)
	avg := total / time.Duration(2*rounds)
	return total, avg
}

func main() {
	const N = 1_000_000

	runtime.GOMAXPROCS(1)
	total1, avg1 := pingPong(N)
	fmt.Printf("GOMAXPROCS=1\n")
	fmt.Printf("  total: %v\n", total1)
	fmt.Printf("  avg per hand-off: %v\n\n", avg1)

	runtime.GOMAXPROCS(runtime.NumCPU())
	total2, avg2 := pingPong(N)
	fmt.Printf("GOMAXPROCS=%d\n", runtime.GOMAXPROCS(0))
	fmt.Printf("  total: %v\n", total2)
	fmt.Printf("  avg per hand-off: %v\n", avg2)
}
