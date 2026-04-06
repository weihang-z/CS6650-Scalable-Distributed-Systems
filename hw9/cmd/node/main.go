package main

import (
	"log"
	"net/http"
	"time"

	"distributed-kv/internal/api"
	"distributed-kv/internal/cluster"
	"distributed-kv/internal/config"
	"distributed-kv/internal/modes"
	"distributed-kv/internal/store"
)

func main() {
	cfg := config.Load()

	memoryStore := store.NewMemoryStore()
	clusterClient := cluster.NewHTTPClient(3 * time.Second)

	var service modes.Service

	switch cfg.Mode {
	case "leader-follower":
		service = modes.NewLeaderFollowerService(cfg, memoryStore, clusterClient)
	case "leaderless":
		service = modes.NewLeaderlessService(cfg, memoryStore, clusterClient)
	default:
		log.Fatalf("unsupported MODE: %s", cfg.Mode)
	}

	server := api.NewServer(service, cfg.NodeID)
	addr := ":" + cfg.Port

	log.Printf("starting node")
	log.Printf("node_id=%s port=%s mode=%s is_leader=%t self_url=%s leader_url=%s N=%d R=%d W=%d nodes=%v",
		cfg.NodeID,
		cfg.Port,
		cfg.Mode,
		cfg.IsLeader,
		cfg.SelfURL,
		cfg.LeaderURL,
		cfg.N,
		cfg.R,
		cfg.W,
		cfg.Nodes,
	)

	if err := http.ListenAndServe(addr, server.Routes()); err != nil {
		log.Fatalf("server failed: %v", err)
	}
}