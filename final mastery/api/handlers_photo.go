package api

import (
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"album-store/models"
	"album-store/store"

	"github.com/google/uuid"
)

type uploadAcceptedResponse struct {
	PhotoID string `json:"photo_id"`
	Seq     uint64 `json:"seq"`
	Status  string `json:"status"`
}

type photoStatusResponse struct {
	PhotoID string `json:"photo_id"`
	AlbumID string `json:"album_id"`
	Seq     uint64 `json:"seq"`
	Status  string `json:"status"`
	URL     string `json:"url,omitempty"`
}

func toPhotoStatusResponse(photo models.Photo) photoStatusResponse {
	return photoStatusResponse{
		PhotoID: photo.PhotoID,
		AlbumID: photo.AlbumID,
		Seq:     photo.Seq,
		Status:  photo.Status,
		URL:     photo.URL,
	}
}

func (s *Server) uploadPhoto(w http.ResponseWriter, r *http.Request) {
	albumID := r.PathValue("album_id")
	if albumID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{
			"error": "missing album_id",
		})
		return
	}

	if !s.store.AlbumExists(albumID) {
		writeJSON(w, http.StatusNotFound, map[string]string{
			"error": "not found",
		})
		return
	}

	photoID := uuid.NewString()
	tempPath := filepath.Join(tempDir, photoID+".upload")

	if err := saveMultipartPhotoToTemp(r, tempPath); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{
			"error": err.Error(),
		})
		return
	}

	publicBaseURL := requestBaseURL(r)

	photo, err := s.store.CreatePhotoProcessing(albumID, photoID, tempPath, publicBaseURL)
	if err != nil {
		_ = os.Remove(tempPath)

		status := http.StatusInternalServerError
		if errors.Is(err, store.ErrAlbumNotFound) {
			status = http.StatusNotFound
		}

		writeJSON(w, status, map[string]string{
			"error": "not found",
		})
		return
	}

	s.jobs <- UploadJob{PhotoID: photo.PhotoID}

	writeJSON(w, http.StatusAccepted, uploadAcceptedResponse{
		PhotoID: photo.PhotoID,
		Seq:     photo.Seq,
		Status:  photo.Status,
	})
}

func (s *Server) getPhotoStatus(w http.ResponseWriter, r *http.Request) {
	albumID := r.PathValue("album_id")
	photoID := r.PathValue("photo_id")

	photo, ok := s.store.GetPhoto(albumID, photoID)
	if !ok {
		writeJSON(w, http.StatusNotFound, map[string]string{
			"error": "not found",
		})
		return
	}

	writeJSON(w, http.StatusOK, toPhotoStatusResponse(photo))
}

func (s *Server) deletePhoto(w http.ResponseWriter, r *http.Request) {
	albumID := r.PathValue("album_id")
	photoID := r.PathValue("photo_id")

	photo, err := s.store.DeletePhoto(albumID, photoID)
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]string{
			"error": "not found",
		})
		return
	}

	_ = removeIfExists(photo.TempPath)
	_ = removeIfExists(photo.FilePath)

	w.WriteHeader(http.StatusNoContent)
}

func (s *Server) startWorkers() {
	for i := 0; i < workerCount; i++ {
		go s.uploadWorker()
	}
}

func (s *Server) uploadWorker() {
	for job := range s.jobs {
		s.processPhoto(job.PhotoID)
	}
}

func (s *Server) processPhoto(photoID string) {
	photo, ok := s.store.GetPhotoByID(photoID)
	if !ok {
		return
	}

	finalPath := filepath.Join(fileDir, photoID+".bin")

	if err := os.Rename(photo.TempPath, finalPath); err != nil {
		_ = s.store.MarkPhotoFailed(photoID)
		return
	}

	url := strings.TrimRight(photo.PublicBaseURL, "/") + "/files/" + photoID

	if _, err := s.store.MarkPhotoCompleted(photoID, finalPath, url); err != nil {
		if errors.Is(err, store.ErrPhotoDeleted) {
			_ = removeIfExists(finalPath)
			return
		}
		_ = removeIfExists(finalPath)
	}
}

func requestBaseURL(r *http.Request) string {
	scheme := "http"
	if r.TLS != nil {
		scheme = "https"
	}

	if forwardedProto := r.Header.Get("X-Forwarded-Proto"); forwardedProto != "" {
		parts := strings.Split(forwardedProto, ",")
		first := strings.TrimSpace(parts[0])
		if first != "" {
			scheme = first
		}
	}

	host := strings.TrimSpace(r.Host)
	return scheme + "://" + host
}

func saveMultipartPhotoToTemp(r *http.Request, tempPath string) (err error) {
	reader, err := r.MultipartReader()
	if err != nil {
		return errors.New("invalid multipart form")
	}

	file, err := os.Create(tempPath)
	if err != nil {
		return fmt.Errorf("failed to create temp file")
	}

	defer func() {
		_ = file.Close()
		if err != nil {
			_ = os.Remove(tempPath)
		}
	}()

	found := false

	for {
		part, nextErr := reader.NextPart()
		if nextErr == io.EOF {
			break
		}
		if nextErr != nil {
			return errors.New("failed to read multipart body")
		}

		if part.FormName() != "photo" {
			_ = part.Close()
			continue
		}

		found = true
		if copyErr := copyPartToFile(file, part); copyErr != nil {
			_ = part.Close()
			return errors.New("failed to save uploaded file")
		}
		_ = part.Close()
		break
	}

	if !found {
		return errors.New("missing photo field")
	}

	return nil
}

func copyPartToFile(dst *os.File, part *multipart.Part) error {
	if _, err := io.Copy(dst, part); err != nil {
		return err
	}
	return dst.Sync()
}

func removeIfExists(path string) error {
	if path == "" {
		return nil
	}
	err := os.Remove(path)
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	return nil
}