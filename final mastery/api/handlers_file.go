package api

import (
	"net/http"

	"album-store/models"
)

func (s *Server) servePhotoFile(w http.ResponseWriter, r *http.Request) {
	photoID := r.PathValue("photo_id")
	if photoID == "" {
		http.NotFound(w, r)
		return
	}

	photo, ok := s.store.GetPhotoByID(photoID)
	if !ok {
		http.NotFound(w, r)
		return
	}

	if photo.Deleted {
		http.NotFound(w, r)
		return
	}

	if photo.Status != models.PhotoStatusCompleted {
		http.NotFound(w, r)
		return
	}

	if photo.FilePath == "" {
		http.NotFound(w, r)
		return
	}

	http.ServeFile(w, r, photo.FilePath)
}