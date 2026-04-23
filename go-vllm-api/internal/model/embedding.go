package model

type EmbeddingRequest struct {
	Model          string   `json:"model"`
	Input          interface{} `json:"input"`
	EncodingFormat string   `json:"encoding_format,omitempty"`
	Dimensions     *int     `json:"dimensions,omitempty"`
}
