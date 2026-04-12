package main

import (
	"log"
	"net/http"
	"os"

	"album-store/api"
	"album-store/store"
)

func main() {
	if err := os.MkdirAll("./data/tmp", 0755); err != nil {
		log.Fatalf("failed to create temp dir: %v", err)
	}
	if err := os.MkdirAll("./data/files", 0755); err != nil {
		log.Fatalf("failed to create file dir: %v", err)
	}

	memStore := store.NewMemoryStore()
	server := api.NewServer(memStore)

	log.Printf("album-store listening on :80")

	if err := http.ListenAndServe(":80", server.Handler()); err != nil {
		log.Fatalf("server failed: %v", err)
	}
}