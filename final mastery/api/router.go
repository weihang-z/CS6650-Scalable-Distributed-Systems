package api

import (
	"net/http"

	"album-store/store"
)

const (
	tempDir      = "./data/tmp"
	fileDir      = "./data/files"
	workerCount  = 4
	jobQueueSize = 512
)

type UploadJob struct {
	PhotoID string
}

type Server struct {
	store *store.MemoryStore
	mux   *http.ServeMux
	jobs  chan UploadJob
}

func NewServer(store *store.MemoryStore) *Server {
	s := &Server{
		store: store,
		mux:   http.NewServeMux(),
		jobs:  make(chan UploadJob, jobQueueSize),
	}

	s.registerRoutes()
	s.startWorkers()

	return s
}

func (s *Server) registerRoutes() {
	s.mux.HandleFunc("GET /health", HealthHandler)

	s.mux.HandleFunc("PUT /albums/{album_id}", s.putAlbum)
	s.mux.HandleFunc("GET /albums/{album_id}", s.getAlbum)
	s.mux.HandleFunc("GET /albums", s.listAlbums)

	s.mux.HandleFunc("POST /albums/{album_id}/photos", s.uploadPhoto)
	s.mux.HandleFunc("GET /albums/{album_id}/photos/{photo_id}", s.getPhotoStatus)
	s.mux.HandleFunc("DELETE /albums/{album_id}/photos/{photo_id}", s.deletePhoto)

	s.mux.HandleFunc("GET /files/{photo_id}", s.servePhotoFile)
}

func (s *Server) Handler() http.Handler {
	return s.mux
}