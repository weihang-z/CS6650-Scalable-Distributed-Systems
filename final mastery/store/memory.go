package store

import (
	"errors"
	"sync"

	"album-store/models"
)

var (
	ErrAlbumNotFound = errors.New("album not found")
	ErrPhotoNotFound = errors.New("photo not found")
	ErrPhotoDeleted  = errors.New("photo deleted")
)

type MemoryStore struct {
	albumsMu   sync.RWMutex
	albumsByID map[string]models.Album
	albumOrder []string
	albumSeq   map[string]uint64

	photosMu   sync.RWMutex
	photosByID map[string]models.Photo
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{
		albumsByID: make(map[string]models.Album),
		albumOrder: make([]string, 0),
		albumSeq:   make(map[string]uint64),
		photosByID: make(map[string]models.Photo),
	}
}

func (s *MemoryStore) PutAlbum(album models.Album) (models.Album, bool) {
	s.albumsMu.Lock()
	defer s.albumsMu.Unlock()

	_, existed := s.albumsByID[album.AlbumID]
	if !existed {
		s.albumOrder = append(s.albumOrder, album.AlbumID)
		s.albumSeq[album.AlbumID] = 0
	}

	s.albumsByID[album.AlbumID] = album
	return album, !existed
}

func (s *MemoryStore) GetAlbum(albumID string) (models.Album, bool) {
	s.albumsMu.RLock()
	defer s.albumsMu.RUnlock()

	album, ok := s.albumsByID[albumID]
	return album, ok
}

func (s *MemoryStore) AlbumExists(albumID string) bool {
	s.albumsMu.RLock()
	defer s.albumsMu.RUnlock()

	_, ok := s.albumsByID[albumID]
	return ok
}

func (s *MemoryStore) ListAlbums() []models.Album {
	s.albumsMu.RLock()
	defer s.albumsMu.RUnlock()

	albums := make([]models.Album, 0, len(s.albumOrder))
	for _, albumID := range s.albumOrder {
		album, ok := s.albumsByID[albumID]
		if ok {
			albums = append(albums, album)
		}
	}
	return albums
}

func (s *MemoryStore) CreatePhotoProcessing(albumID, photoID, tempPath, publicBaseURL string) (models.Photo, error) {
	s.albumsMu.Lock()
	_, ok := s.albumsByID[albumID]
	if !ok {
		s.albumsMu.Unlock()
		return models.Photo{}, ErrAlbumNotFound
	}

	s.albumSeq[albumID]++
	seq := s.albumSeq[albumID]
	s.albumsMu.Unlock()

	photo := models.Photo{
		PhotoID:       photoID,
		AlbumID:       albumID,
		Seq:           seq,
		Status:        models.PhotoStatusProcessing,
		TempPath:      tempPath,
		PublicBaseURL: publicBaseURL,
	}

	s.photosMu.Lock()
	s.photosByID[photoID] = photo
	s.photosMu.Unlock()

	return photo, nil
}

func (s *MemoryStore) GetPhoto(albumID, photoID string) (models.Photo, bool) {
	s.photosMu.RLock()
	defer s.photosMu.RUnlock()

	photo, ok := s.photosByID[photoID]
	if !ok {
		return models.Photo{}, false
	}
	if photo.Deleted {
		return models.Photo{}, false
	}
	if photo.AlbumID != albumID {
		return models.Photo{}, false
	}
	return photo, true
}

func (s *MemoryStore) GetPhotoByID(photoID string) (models.Photo, bool) {
	s.photosMu.RLock()
	defer s.photosMu.RUnlock()

	photo, ok := s.photosByID[photoID]
	return photo, ok
}

func (s *MemoryStore) MarkPhotoCompleted(photoID, filePath, url string) (models.Photo, error) {
	s.photosMu.Lock()
	defer s.photosMu.Unlock()

	photo, ok := s.photosByID[photoID]
	if !ok {
		return models.Photo{}, ErrPhotoNotFound
	}
	if photo.Deleted {
		return models.Photo{}, ErrPhotoDeleted
	}

	photo.Status = models.PhotoStatusCompleted
	photo.URL = url
	photo.FilePath = filePath
	photo.TempPath = ""

	s.photosByID[photoID] = photo
	return photo, nil
}

func (s *MemoryStore) MarkPhotoFailed(photoID string) error {
	s.photosMu.Lock()
	defer s.photosMu.Unlock()

	photo, ok := s.photosByID[photoID]
	if !ok {
		return ErrPhotoNotFound
	}
	if photo.Deleted {
		return nil
	}

	photo.Status = models.PhotoStatusFailed
	s.photosByID[photoID] = photo
	return nil
}

func (s *MemoryStore) DeletePhoto(albumID, photoID string) (models.Photo, error) {
	s.photosMu.Lock()
	defer s.photosMu.Unlock()

	photo, ok := s.photosByID[photoID]
	if !ok {
		return models.Photo{}, ErrPhotoNotFound
	}
	if photo.Deleted {
		return models.Photo{}, ErrPhotoNotFound
	}
	if photo.AlbumID != albumID {
		return models.Photo{}, ErrPhotoNotFound
	}

	photo.Deleted = true
	photo.URL = ""

	s.photosByID[photoID] = photo
	return photo, nil
}