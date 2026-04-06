package modes

import (
	"context"
	"errors"

	"distributed-kv/internal/store"
)

var (
	ErrKeyNotFound            = errors.New("key not found")
	ErrWriteOnFollower        = errors.New("writes must go to the leader")
	ErrNotEnoughWriteAcks     = errors.New("not enough write acknowledgements")
	ErrNotEnoughReadResponses = errors.New("not enough read responses")
	ErrUnsupportedWriteConcern = errors.New("unsupported write concern")
	ErrUnsupportedReadConcern  = errors.New("unsupported read concern")
)

type Service interface {
	ClientSet(ctx context.Context, key string, value string) (store.Record, error)
	ClientGet(ctx context.Context, key string) (store.Record, error)

	LocalRead(key string) (store.Record, bool)

	InternalReplicate(ctx context.Context, key string, record store.Record) (bool, error)
	InternalRead(ctx context.Context, key string) (store.Record, bool, error)
}