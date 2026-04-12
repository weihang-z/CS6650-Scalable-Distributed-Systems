package modes

import (
	"context"
	"log"
	"sync/atomic"
	"time"

	"distributed-kv/internal/cluster"
	"distributed-kv/internal/config"
	"distributed-kv/internal/store"
)

type LeaderFollowerService struct {
	store         *store.MemoryStore
	clusterClient cluster.Client

	selfURL   string
	leaderURL string
	allNodes  []string

	isLeader bool
	readW    int
	writeW   int

	nextVersion atomic.Int64

	afterFollowerMessageDelay time.Duration
	followerApplyDelay        time.Duration
	followerReadDelay         time.Duration
}

func NewLeaderFollowerService(
	cfg config.Config,
	memoryStore *store.MemoryStore,
	clusterClient cluster.Client,
) *LeaderFollowerService {
	return &LeaderFollowerService{
		store:         memoryStore,
		clusterClient: clusterClient,

		selfURL:   cfg.SelfURL,
		leaderURL: cfg.LeaderURL,
		allNodes:  append([]string(nil), cfg.Nodes...),

		isLeader: cfg.IsLeader,
		readW:    cfg.R,
		writeW:   cfg.W,

		afterFollowerMessageDelay: 200 * time.Millisecond,
		followerApplyDelay:        100 * time.Millisecond,
		followerReadDelay:         50 * time.Millisecond,
	}
}

func (s *LeaderFollowerService) ClientSet(ctx context.Context, key string, value string) (store.Record, error) {
	if !s.isLeader {
		return store.Record{}, ErrWriteOnFollower
	}

	record := store.Record{
		Value:   value,
		Version: s.nextVersion.Add(1),
	}

	// Leader always writes locally first.
	s.store.Put(key, record)

	followerURLs := s.followerURLs()

	switch s.writeW {
	case 1:
		go s.propagateInBackground(key, record, followerURLs)
		return record, nil

	case 3, 5:
		ackCount := 1
		nextIndex := 0

		for nextIndex < len(followerURLs) {
			err := s.replicateToFollower(ctx, followerURLs[nextIndex], key, record)
			if err == nil {
				ackCount++
			}

			nextIndex++

			if ackCount >= s.writeW {
				break
			}
		}

		if ackCount < s.writeW {
			return store.Record{}, ErrNotEnoughWriteAcks
		}

		// Even if we already reached W, the leader should still replicate to all remaining followers.
		if nextIndex < len(followerURLs) {
			remaining := append([]string(nil), followerURLs[nextIndex:]...)
			go s.propagateInBackground(key, record, remaining)
		}

		return record, nil

	default:
		return store.Record{}, ErrUnsupportedWriteConcern
	}
}

func (s *LeaderFollowerService) ClientGet(ctx context.Context, key string) (store.Record, error) {
	switch s.readW {
	case 1:
		return s.readFromLeader(ctx, key)

	case 3:
		return s.readMostRecent(ctx, key, s.allNodes, 3)

	case 5:
		return s.readMostRecent(ctx, key, s.allNodes, 5)

	default:
		return store.Record{}, ErrUnsupportedReadConcern
	}
}

func (s *LeaderFollowerService) LocalRead(key string) (store.Record, bool) {
	return s.store.Get(key)
}

func (s *LeaderFollowerService) InternalReplicate(ctx context.Context, key string, record store.Record) (bool, error) {
	// In leader-follower mode, internal replication targets followers.
	// The spec says followers sleep 100ms before responding.
	if !s.isLeader {
		time.Sleep(s.followerApplyDelay)
	}

	applied := s.store.PutIfNewer(key, record)
	return applied, nil
}

func (s *LeaderFollowerService) InternalRead(ctx context.Context, key string) (store.Record, bool, error) {
	// The spec says followers sleep 50ms before responding to leader-driven reads.
	// We model this as: followers delay on internal reads, leader does not.
	if !s.isLeader {
		time.Sleep(s.followerReadDelay)
	}

	record, exists := s.store.Get(key)
	return record, exists, nil
}

func (s *LeaderFollowerService) followerURLs() []string {
	result := make([]string, 0, len(s.allNodes))
	for _, nodeURL := range s.allNodes {
		if nodeURL != s.selfURL {
			result = append(result, nodeURL)
		}
	}
	return result
}


func (s *LeaderFollowerService) readFromLeader(ctx context.Context, key string) (store.Record, error) {
	if s.selfURL == s.leaderURL {
		record, exists := s.store.Get(key)
		if !exists {
			return store.Record{}, ErrKeyNotFound
		}
		return record, nil
	}

	result, err := s.clusterClient.InternalRead(ctx, s.leaderURL, key)
	if err != nil {
		return store.Record{}, ErrNotEnoughReadResponses
	}

	if !result.Found {
		return store.Record{}, ErrKeyNotFound
	}

	return result.Record, nil
}

func (s *LeaderFollowerService) readMostRecent(
	ctx context.Context,
	key string,
	candidates []string,
	requiredResponses int,
) (store.Record, error) {
	successCount := 0
	foundAny := false
	var newest store.Record

	seen := make(map[string]bool)

	for _, nodeURL := range candidates {
		if seen[nodeURL] {
			continue
		}
		seen[nodeURL] = true

		result, err := s.readOne(ctx, nodeURL, key)
		if err != nil {
			continue
		}

		successCount++

		if result.Found {
			if !foundAny || result.Record.Version > newest.Version {
				newest = result.Record
				foundAny = true
			}
		}

		if successCount >= requiredResponses {
			break
		}
	}

	if successCount < requiredResponses {
		return store.Record{}, ErrNotEnoughReadResponses
	}

	if !foundAny {
		return store.Record{}, ErrKeyNotFound
	}

	return newest, nil
}

func (s *LeaderFollowerService) readOne(ctx context.Context, nodeURL string, key string) (cluster.ReadResult, error) {
	if nodeURL == s.selfURL {
		record, exists := s.store.Get(key)
		return cluster.ReadResult{
			NodeURL: nodeURL,
			NodeID:  "",
			Key:     key,
			Record:  record,
			Found:   exists,
		}, nil
	}

	return s.clusterClient.InternalRead(ctx, nodeURL, key)
}

func (s *LeaderFollowerService) replicateToFollower(
	ctx context.Context,
	followerURL string,
	key string,
	record store.Record,
) error {
	_, err := s.clusterClient.Replicate(ctx, followerURL, key, record)

	// Spec: the leader should sleep for 200ms following each message to a follower.
	time.Sleep(s.afterFollowerMessageDelay)

	return err
}

func (s *LeaderFollowerService) propagateInBackground(key string, record store.Record, followers []string) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	for _, followerURL := range followers {
		if err := s.replicateToFollower(ctx, followerURL, key, record); err != nil {
			log.Printf("background replication failed to %s for key=%s version=%d: %v",
				followerURL, key, record.Version, err)
		}
	}
}