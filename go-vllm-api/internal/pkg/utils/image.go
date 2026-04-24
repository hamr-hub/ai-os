package utils

import (
	"bytes"
	"encoding/base64"
	"fmt"
	"image"
	_ "image/gif"
	_ "image/jpeg"
	_ "image/png"
	"regexp"
	"strings"

	"go-vllm-api/internal/model"

	_ "golang.org/x/image/bmp"
	_ "golang.org/x/image/tiff"
	_ "golang.org/x/image/webp"
)

var base64Regex = regexp.MustCompile(`^data:image/([\w-]+);base64,(.+)$`)

func ValidateImageData(imageData []byte) model.ImageValidationResponse {
	img, format, err := image.DecodeConfig(bytes.NewReader(imageData))
	if err != nil {
		return model.ImageValidationResponse{
			Valid: false,
			Error: fmt.Sprintf("Invalid image data: %v", err),
		}
	}

	format = strings.ToLower(format)
	if !model.SupportedFormats[format] {
		return model.ImageValidationResponse{
			Valid: false,
			Error: fmt.Sprintf("Unsupported image format: %s", format),
		}
	}

	if img.Width > model.MaxWidth || img.Height > model.MaxHeight {
		return model.ImageValidationResponse{
			Valid: false,
			Error: fmt.Sprintf("Image dimensions exceed maximum allowed size. Max: %dx%d, Got: %dx%d", 
				model.MaxWidth, model.MaxHeight, img.Width, img.Height),
		}
	}

	return model.ImageValidationResponse{
		Valid:     true,
		Width:     img.Width,
		Height:    img.Height,
		Format:    format,
		SizeBytes: len(imageData),
	}
}

func DecodeBase64Image(base64String string) ([]byte, error) {
	var base64Data string
	matches := base64Regex.FindStringSubmatch(base64String)
	if len(matches) > 2 {
		base64Data = matches[2]
	} else {
		base64Data = base64String
	}

	decoded, err := base64.StdEncoding.DecodeString(base64Data)
	if err != nil {
		return nil, fmt.Errorf("failed to decode base64: %w", err)
	}

	if len(decoded) > model.MaxImageSizeBytes {
		return nil, fmt.Errorf("image size exceeds maximum allowed size of %dMB", model.MaxImageSizeMB)
	}

	return decoded, nil
}

func CountImageContent(req model.ChatCompletionRequest) (bool, int) {
	hasImage := false
	totalSize := 0

	for _, message := range req.Messages {
		if message.Content.List != nil {
			for _, part := range message.Content.List {
				if part.Type == "image_url" && part.ImageURL != nil {
					hasImage = true
					url := part.ImageURL.URL
					if strings.HasPrefix(url, "data:image/") {
						idx := strings.Index(url, ",")
						if idx > 0 {
							base64Data := url[idx+1:]
							// Approximate size of decoded base64
							totalSize += (len(base64Data) * 3) / 4
						}
					}
				}
			}
		}
	}
	return hasImage, totalSize
}

var MultimodalModels = map[string]bool{
	"gemma-2-vision":                   true,
	"llava":                            true,
	"qwen-vl":                          true,
	"internvl":                         true,
	"cogvlm":                           true,
	"gemma-4-31b-abliterated":          true,
	"qwen3-235b-a22b-instruct-2507-awq": true,
}

func IsMultimodalModel(modelName string) bool {
	return MultimodalModels[strings.ToLower(modelName)]
}
