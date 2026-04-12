package api

import (
	"encoding/json"
	"net/http"

	"album-store/models"
)

func (s *Server) putAlbum(w http.ResponseWriter, r *http.Request) {
	albumID := r.PathValue("album_id")
	if albumID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{
			"error": "missing album_id",
		})
		return
	}

	var req models.Album
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{
			"error": "invalid json",
		})
		return
	}

	album := models.Album{
		AlbumID:     albumID,
		Title:       req.Title,
		Description: req.Description,
		Owner:       req.Owner,
	}

	stored, created := s.store.PutAlbum(album)
	if created {
		writeJSON(w, http.StatusCreated, stored)
		return
	}

	writeJSON(w, http.StatusOK, stored)
}

func (s *Server) getAlbum(w http.ResponseWriter, r *http.Request) {
	albumID := r.PathValue("album_id")
	if albumID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{
			"error": "missing album_id",
		})
		return
	}

	album, ok := s.store.GetAlbum(albumID)
	if !ok {
		writeJSON(w, http.StatusNotFound, map[string]string{
			"error": "not found",
		})
		return
	}

	writeJSON(w, http.StatusOK, album)
}

func (s *Server) listAlbums(w http.ResponseWriter, r *http.Request) {
	albums := s.store.ListAlbums()
	writeJSON(w, http.StatusOK, albums)
}