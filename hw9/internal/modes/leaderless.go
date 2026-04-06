package modes

import (
	"context"
	"time"

	"distributed-kv/internal/cluster"
	"distributed-kv/internal/config"
	"distributed-kv/internal/store"
)

type LeaderlessService struct {
	store         *store.MemoryStore
	clusterClient cluster.Client

	selfURL  string
	allNodes []string

	afterPeerMessageDelay time.Duration
	peerApplyDelay        time.Duration
}

func (s *LeaderlessService) InternalRead(ctx context.Context, key string) (store.Record, bool, error) {
	return store.Record{}, true, nil
}

func NewLeaderlessService(
	cfg config.Config,
	memoryStore *store.MemoryStore,
	clusterClient cluster.Client,
) *LeaderlessService {
	return &LeaderlessService{
		store:         memoryStore,
		clusterClient: clusterClient,

		selfURL:  cfg.SelfURL,
		allNodes: append([]string(nil), cfg.Nodes...),

		afterPeerMessageDelay: 200 * time.Millisecond,
		peerApplyDelay:        100 * time.Millisecond,
	}
}

func (s *LeaderlessService) ClientSet(ctx context.Context, key string, value string) (store.Record, error) {
	record := store.Record{
		Value:   value,
		Version: time.Now().UnixNano(),
	}

	// The receiving node becomes the write coordinator and writes locally first.
	s.store.Put(key, record)

	peerURLs := s.peerURLs()

	for _, peerURL := range peerURLs {
		s.replicateToPeer(ctx, peerURL, key, record)
	}

	return record, nil
}

func (s *LeaderlessService) ClientGet(ctx context.Context, key string) (store.Record, error) {
	record, exists := s.store.Get(key)
	if !exists {
		return store.Record{}, ErrKeyNotFound
	}
	return record, nil
}

func (s *LeaderlessService) LocalRead(key string) (store.Record, bool) {
	return s.store.Get(key)
}

func (s *LeaderlessService) InternalReplicate(ctx context.Context, key string, record store.Record) (bool, error) {
	time.Sleep(s.peerApplyDelay)

	applied := s.store.PutIfNewer(key, record)
	return applied, nil
}

func (s *LeaderlessService) peerURLs() []string {
	result := make([]string, 0, len(s.allNodes))
	for _, nodeURL := range s.allNodes {
		if nodeURL != s.selfURL {
			result = append(result, nodeURL)
		}
	}
	return result
}

func (s *LeaderlessService) replicateToPeer(
	ctx context.Context,
	peerURL string,
	key string,
	record store.Record,
) error {
	_, err := s.clusterClient.Replicate(ctx, peerURL, key, record)

	time.Sleep(s.afterPeerMessageDelay)

	return err
}
