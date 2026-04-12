package models

const (
	PhotoStatusProcessing = "processing"
	PhotoStatusCompleted  = "completed"
	PhotoStatusFailed     = "failed"
)

type Album struct {
	AlbumID     string `json:"album_id"`
	Title       string `json:"title"`
	Description string `json:"description"`
	Owner       string `json:"owner"`
}

type Photo struct {
	PhotoID       string `json:"photo_id"`
	AlbumID       string `json:"album_id"`
	Seq           uint64 `json:"seq"`
	Status        string `json:"status"`
	URL           string `json:"url,omitempty"`

	TempPath      string `json:"-"`
	FilePath      string `json:"-"`
	PublicBaseURL string `json:"-"`

	Deleted       bool   `json:"-"`
}