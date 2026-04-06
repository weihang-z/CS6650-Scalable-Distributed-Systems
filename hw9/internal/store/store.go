package store

import "sync"

type MemoryStore struct {
	mu   sync.RWMutex
	data map[string]Record
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{
		data: make(map[string]Record),
	}
}

func (s *MemoryStore) Get(key string) (Record, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	record, exists := s.data[key]
	return record, exists
}

func (s *MemoryStore) Put(key string, record Record) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.data[key] = record
}

func (s *MemoryStore) PutIfNewer(key string, incoming Record) bool {
	s.mu.Lock()
	defer s.mu.Unlock()

	current, exists := s.data[key]
	if !exists || incoming.Version >= current.Version {
		s.data[key] = incoming
		return true
	}

	return false
}