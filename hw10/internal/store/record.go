package store

type Record struct {
	Value   string `json:"value"`
	Version int64  `json:"version"`
}