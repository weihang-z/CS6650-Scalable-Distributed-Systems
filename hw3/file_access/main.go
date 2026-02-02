package main

import (
	"bufio"
	"fmt"
	"os"
	"time"
)


func writeUnbuffered(path string, n int) (time.Duration, error) {
	f, _ := os.Create(path)

	start := time.Now()

	for range n {
		f.Write([]byte("hello world\n"))
	}
	f.Close()
	return time.Since(start), nil
}

func writeBuffered(path string, n int) (time.Duration, error) {
	f, _ := os.OpenFile(path, os.O_WRONLY|os.O_TRUNC, 0644)

	w := bufio.NewWriter(f)

	start := time.Now()

	for i := 0; i < n; i++ {
		w.WriteString("hello world\n")
	}

	w.Flush()
	f.Close()
	return time.Since(start), nil
}

func main() {
	d1, _ := writeUnbuffered("output.txt", 100000)

	d2, _ := writeBuffered("output.txt", 100000)

	fmt.Println("unbuffered:", d1)
	fmt.Println("buffered:  ", d2)
}
