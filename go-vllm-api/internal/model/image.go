package model

const (
	MaxImageSizeMB   = 10
	MaxImageSizeBytes = MaxImageSizeMB * 1024 * 1024
	MaxWidth         = 8192
	MaxHeight        = 8192
)

var SupportedFormats = map[string]bool{
	"png": true, "jpg": true, "jpeg": true, "gif": true,
	"webp": true, "bmp": true, "tiff": true,
}

type ImageGenerationRequest struct {
	Model           string `json:"model"`
	Prompt          string `json:"prompt"`
	N               int    `json:"n,omitempty"`
	Size            string `json:"size,omitempty"`
	ResponseFormat  string `json:"response_format,omitempty"`
}

type ImageGenerationResponse struct {
	Created int64        `json:"created"`
	Data    []ImageData  `json:"data"`
}

type ImageData struct {
	URL           string `json:"url,omitempty"`
	B64JSON       string `json:"b64_json,omitempty"`
	RevisedPrompt string `json:"revised_prompt,omitempty"`
}

type ImageValidationRequest struct {
	ImageData string `json:"image_data"`
}

type ImageUploadResponse struct {
	Success   bool        `json:"success"`
	Message   string      `json:"message"`
	ImageInfo interface{} `json:"image_info,omitempty"`
}
