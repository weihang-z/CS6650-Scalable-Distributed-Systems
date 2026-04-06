package config

import (
	"log"
	"os"
	"strconv"
	"strings"
)

type Config struct {
	NodeID    string
	Port      string
	Mode      string
	IsLeader  bool
	SelfURL   string
	LeaderURL string
	N         int
	R         int
	W         int
	Nodes     []string
}

func Load() Config {
	port := getEnv("PORT", "8080")
	selfURL := getEnv("SELF_URL", "http://localhost:"+port)
	isLeader := getEnvAsBool("IS_LEADER", false)

	leaderFallback := ""
	if isLeader {
		leaderFallback = selfURL
	}

	return Config{
		NodeID:    getEnv("NODE_ID", "node1"),
		Port:      port,
		Mode:      getEnv("MODE", "leader-follower"),
		IsLeader:  isLeader,
		SelfURL:   selfURL,
		LeaderURL: getEnv("LEADER_URL", leaderFallback),
		N:         getEnvAsInt("N", 5),
		R:         getEnvAsInt("R", 1),
		W:         getEnvAsInt("W", 5),
		Nodes:     getEnvAsSlice("NODES", []string{selfURL}),
	}
}

func getEnv(key string, fallback string) string {
	value, exists := os.LookupEnv(key)
	if !exists {
		return fallback
	}
	return value
}

func getEnvAsBool(key string, fallback bool) bool {
	value, exists := os.LookupEnv(key)
	if !exists {
		return fallback
	}

	parsed, err := strconv.ParseBool(value)
	if err != nil {
		log.Fatalf("invalid boolean for %s: %v", key, err)
	}

	return parsed
}

func getEnvAsInt(key string, fallback int) int {
	value, exists := os.LookupEnv(key)
	if !exists {
		return fallback
	}

	parsed, err := strconv.Atoi(value)
	if err != nil {
		log.Fatalf("invalid integer for %s: %v", key, err)
	}

	return parsed
}

func getEnvAsSlice(key string, fallback []string) []string {
	value, exists := os.LookupEnv(key)
	if !exists || strings.TrimSpace(value) == "" {
		return fallback
	}

	parts := strings.Split(value, ",")
	result := make([]string, 0, len(parts))

	for _, part := range parts {
		trimmed := strings.TrimSpace(part)
		if trimmed != "" {
			result = append(result, trimmed)
		}
	}

	return result
}