package cluster

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	"distributed-kv/internal/store"
)

type Client interface {
	Replicate(ctx context.Context, nodeURL string, key string, record store.Record) (ReplicateResult, error)
	InternalRead(ctx context.Context, nodeURL string, key string) (ReadResult, error)
}

type HTTPClient struct {
	client *http.Client
}

type replicateRequest struct {
	Value   string `json:"value"`
	Version int64  `json:"version"`
}

type replicateResponse struct {
	Key     string `json:"key"`
	Applied bool   `json:"applied"`
	Value   string `json:"value"`
	Version int64  `json:"version"`
	NodeID  string `json:"node_id"`
	Message string `json:"message"`
}

type valueResponse struct {
	Key     string `json:"key"`
	Value   string `json:"value"`
	Version int64  `json:"version"`
	NodeID  string `json:"node_id"`
}

type errorResponse struct {
	Error string `json:"error"`
}

type ReplicateResult struct {
	NodeURL    string
	NodeID     string
	Key        string
	Applied    bool
	Version    int64
	StatusCode int
	Message    string
}

type ReadResult struct {
	NodeURL    string
	NodeID     string
	Key        string
	Record     store.Record
	Found      bool
	StatusCode int
}

func NewHTTPClient(timeout time.Duration) *HTTPClient {
	return &HTTPClient{
		client: &http.Client{
			Timeout: timeout,
		},
	}
}

func (c *HTTPClient) Replicate(ctx context.Context, nodeURL string, key string, record store.Record) (ReplicateResult, error) {
	endpoint := buildURL(nodeURL, "/internal/replicate/", key)

	reqBody := replicateRequest{
		Value:   record.Value,
		Version: record.Version,
	}

	payload, err := json.Marshal(reqBody)
	if err != nil {
		return ReplicateResult{}, fmt.Errorf("marshal replicate request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPut, endpoint, bytes.NewReader(payload))
	if err != nil {
		return ReplicateResult{}, fmt.Errorf("create replicate request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return ReplicateResult{}, fmt.Errorf("send replicate request to %s: %w", nodeURL, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return ReplicateResult{}, fmt.Errorf("replicate request to %s returned status %d: %s", nodeURL, resp.StatusCode, resp.Body)
	}

	var decoded replicateResponse
	if err := json.NewDecoder(resp.Body).Decode(&decoded); err != nil {
		return ReplicateResult{}, fmt.Errorf("decode replicate response from %s: %w", nodeURL, err)
	}

	return ReplicateResult{
		NodeURL:    nodeURL,
		NodeID:     decoded.NodeID,
		Key:        decoded.Key,
		Applied:    decoded.Applied,
		Version:    decoded.Version,
		StatusCode: resp.StatusCode,
		Message:    decoded.Message,
	}, nil
}

func (c *HTTPClient) InternalRead(ctx context.Context, nodeURL string, key string) (ReadResult, error) {
	endpoint := buildURL(nodeURL, "/internal/read/", key)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return ReadResult{}, fmt.Errorf("create internal read request: %w", err)
	}

	resp, err := c.client.Do(req)
	if err != nil {
		return ReadResult{}, fmt.Errorf("send internal read request to %s: %w", nodeURL, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return ReadResult{
			NodeURL:    nodeURL,
			Found:      false,
			StatusCode: resp.StatusCode,
		}, nil
	}

	if resp.StatusCode != http.StatusOK {
		return ReadResult{}, fmt.Errorf("internal read request to %s returned status %d", nodeURL, resp.StatusCode)
	}

	var decoded valueResponse
	if err := json.NewDecoder(resp.Body).Decode(&decoded); err != nil {
		return ReadResult{}, fmt.Errorf("decode internal read response from %s: %w", nodeURL, err)
	}

	return ReadResult{
		NodeURL: nodeURL,
		NodeID:  decoded.NodeID,
		Key:     decoded.Key,
		Record: store.Record{
			Value:   decoded.Value,
			Version: decoded.Version,
		},
		Found:      true,
		StatusCode: resp.StatusCode,
	}, nil
}

func buildURL(baseURL string, prefix string, key string) string {
	trimmed := strings.TrimRight(baseURL, "/")
	escapedKey := url.PathEscape(key)
	return trimmed + prefix + escapedKey
}
