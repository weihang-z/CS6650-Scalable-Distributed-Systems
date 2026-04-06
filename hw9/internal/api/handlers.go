package api

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/url"
	"strings"

	"distributed-kv/internal/modes"
	"distributed-kv/internal/store"
)

type Server struct {
	service modes.Service
	nodeID  string
}

type setValueRequest struct {
	Value string `json:"value"`
}

type replicateRequest struct {
	Value   string `json:"value"`
	Version int64  `json:"version"`
}

type valueResponse struct {
	Key     string `json:"key"`
	Value   string `json:"value"`
	Version int64  `json:"version"`
	NodeID  string `json:"node_id"`
}

type replicateResponse struct {
	Key     string `json:"key"`
	Applied bool   `json:"applied"`
	Value   string `json:"value"`
	Version int64  `json:"version"`
	NodeID  string `json:"node_id"`
	Message string `json:"message"`
}

type errorResponse struct {
	Error string `json:"error"`
}

func NewServer(service modes.Service, nodeID string) *Server {
	return &Server{
		service: service,
		nodeID:  nodeID,
	}
}

func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/kv/", s.handleKV)
	mux.HandleFunc("/local_read/", s.handleLocalRead)
	mux.HandleFunc("/internal/replicate/", s.handleInternalReplicate)
	mux.HandleFunc("/internal/read/", s.handleInternalRead)

	return mux
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, errorResponse{
			Error: "method not allowed",
		})
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{
		"status": "ok",
		"node":   s.nodeID,
	})
}

func (s *Server) handleKV(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodPut:
		s.handleSet(w, r)
	case http.MethodGet:
		s.handleGet(w, r)
	default:
		writeJSON(w, http.StatusMethodNotAllowed, errorResponse{
			Error: "method not allowed",
		})
	}
}

func (s *Server) handleSet(w http.ResponseWriter, r *http.Request) {
	key, ok := extractKey(r.URL.Path, "/kv/")
	if !ok {
		writeJSON(w, http.StatusBadRequest, errorResponse{
			Error: "key cannot be empty",
		})
		return
	}

	var req setValueRequest

	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()

	if err := decoder.Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, errorResponse{
			Error: "invalid JSON body",
		})
		return
	}

	record, err := s.service.ClientSet(r.Context(), key, req.Value)
	if err != nil {
		s.writeServiceError(w, err)
		return
	}

	writeJSON(w, http.StatusCreated, valueResponse{
		Key:     key,
		Value:   record.Value,
		Version: record.Version,
		NodeID:  s.nodeID,
	})
}

func (s *Server) handleGet(w http.ResponseWriter, r *http.Request) {
	key, ok := extractKey(r.URL.Path, "/kv/")
	if !ok {
		writeJSON(w, http.StatusBadRequest, errorResponse{
			Error: "key cannot be empty",
		})
		return
	}

	record, err := s.service.ClientGet(r.Context(), key)
	if err != nil {
		s.writeServiceError(w, err)
		return
	}

	writeJSON(w, http.StatusOK, valueResponse{
		Key:     key,
		Value:   record.Value,
		Version: record.Version,
		NodeID:  s.nodeID,
	})
}

func (s *Server) handleLocalRead(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, errorResponse{
			Error: "method not allowed",
		})
		return
	}

	key, ok := extractKey(r.URL.Path, "/local_read/")
	if !ok {
		writeJSON(w, http.StatusBadRequest, errorResponse{
			Error: "key cannot be empty",
		})
		return
	}

	record, exists := s.service.LocalRead(key)
	if !exists {
		writeJSON(w, http.StatusNotFound, errorResponse{
			Error: "key not found",
		})
		return
	}

	writeJSON(w, http.StatusOK, valueResponse{
		Key:     key,
		Value:   record.Value,
		Version: record.Version,
		NodeID:  s.nodeID,
	})
}

func (s *Server) handleInternalReplicate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		writeJSON(w, http.StatusMethodNotAllowed, errorResponse{
			Error: "method not allowed",
		})
		return
	}

	key, ok := extractKey(r.URL.Path, "/internal/replicate/")
	if !ok {
		writeJSON(w, http.StatusBadRequest, errorResponse{
			Error: "key cannot be empty",
		})
		return
	}

	var req replicateRequest

	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()

	if err := decoder.Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, errorResponse{
			Error: "invalid JSON body",
		})
		return
	}

	if req.Version <= 0 {
		writeJSON(w, http.StatusBadRequest, errorResponse{
			Error: "version must be positive",
		})
		return
	}

	incoming := store.Record{
		Value:   req.Value,
		Version: req.Version,
	}

	applied, err := s.service.InternalReplicate(r.Context(), key, incoming)
	if err != nil {
		s.writeServiceError(w, err)
		return
	}

	message := "replica updated"
	if !applied {
		message = "stale replica update ignored"
	}

	writeJSON(w, http.StatusOK, replicateResponse{
		Key:     key,
		Applied: applied,
		Value:   incoming.Value,
		Version: incoming.Version,
		NodeID:  s.nodeID,
		Message: message,
	})
}

func (s *Server) handleInternalRead(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, errorResponse{
			Error: "method not allowed",
		})
		return
	}

	key, ok := extractKey(r.URL.Path, "/internal/read/")
	if !ok {
		writeJSON(w, http.StatusBadRequest, errorResponse{
			Error: "key cannot be empty",
		})
		return
	}

	record, exists, err := s.service.InternalRead(r.Context(), key)
	if err != nil {
		s.writeServiceError(w, err)
		return
	}

	if !exists {
		writeJSON(w, http.StatusNotFound, errorResponse{
			Error: "key not found",
		})
		return
	}

	writeJSON(w, http.StatusOK, valueResponse{
		Key:     key,
		Value:   record.Value,
		Version: record.Version,
		NodeID:  s.nodeID,
	})
}

func (s *Server) writeServiceError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, modes.ErrKeyNotFound):
		writeJSON(w, http.StatusNotFound, errorResponse{Error: err.Error()})
	case errors.Is(err, modes.ErrWriteOnFollower):
		writeJSON(w, http.StatusForbidden, errorResponse{Error: err.Error()})
	case errors.Is(err, modes.ErrNotEnoughWriteAcks),
		errors.Is(err, modes.ErrNotEnoughReadResponses):
		writeJSON(w, http.StatusServiceUnavailable, errorResponse{Error: err.Error()})
	default:
		writeJSON(w, http.StatusInternalServerError, errorResponse{Error: err.Error()})
	}
}

func extractKey(path string, prefix string) (string, bool) {
	if !strings.HasPrefix(path, prefix) {
		return "", false
	}

	rawKey := strings.TrimPrefix(path, prefix)
	if rawKey == "" {
		return "", false
	}

	key, err := url.PathUnescape(rawKey)
	if err != nil || key == "" {
		return "", false
	}

	return key, true
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)

	_ = json.NewEncoder(w).Encode(payload)
}