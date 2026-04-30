package v1

import (
	"testing"

	"go-vllm-api/internal/model"
)

func TestEstimateInputTokens(t *testing.T) {
	h := &V1Handler{}

	textContent := "Hello, how are you today?"
	req := model.ChatCompletionRequest{
		Messages: []model.ChatMessage{
			{
				Role: "user",
				Content: model.ContentVal{Str: &textContent},
			},
		},
	}

	estimated := h.estimateInputTokens(req)
	expectedMin := len(textContent) / 4
	if estimated < expectedMin || estimated == 0 {
		t.Errorf("estimateInputTokens for simple text: got %d, expected >= %d", estimated, expectedMin)
	}
}

func TestEstimateInputTokensMultimodal(t *testing.T) {
	h := &V1Handler{}

	req := model.ChatCompletionRequest{
		Messages: []model.ChatMessage{
			{
				Role: "user",
				Content: model.ContentVal{
					List: []model.ContentPart{
						{Type: "text", Text: "What is in this image?"},
						{Type: "image_url", ImageURL: &model.ImageURLPart{URL: "data:image/png;base64,abc"}},
					},
				},
			},
		},
	}

	estimated := h.estimateInputTokens(req)
	if estimated == 0 {
		t.Errorf("estimateInputTokens for multimodal: got 0, expected > 0")
	}
	if estimated != len("What is in this image?")/4 {
		t.Errorf("estimateInputTokens should only count text parts, not image URLs")
	}
}

func TestEstimateInputTokensEmpty(t *testing.T) {
	h := &V1Handler{}

	req := model.ChatCompletionRequest{
		Messages: []model.ChatMessage{},
	}

	estimated := h.estimateInputTokens(req)
	if estimated != 0 {
		t.Errorf("estimateInputTokens for empty messages: got %d, expected 0", estimated)
	}
}

func TestEstimateInputTokensWithTools(t *testing.T) {
	h := &V1Handler{}

	req := model.ChatCompletionRequest{
		Messages: []model.ChatMessage{
			{
				Role: "user",
				Content: model.ContentVal{Str: ptrStr("Search for flights")},
			},
		},
		Tools: []model.ToolDefinition{
			{
				Type: "function",
				Function: model.ToolFunction{
					Name:        "search_flights",
					Description: "Search for available flights",
				},
			},
		},
	}

	estimated := h.estimateInputTokens(req)
	if estimated == 0 {
		t.Errorf("estimateInputTokens with tools: got 0, expected > 0")
	}
}

func TestEstimateInputTokensWithToolCalls(t *testing.T) {
	h := &V1Handler{}

	req := model.ChatCompletionRequest{
		Messages: []model.ChatMessage{
			{
				Role: "assistant",
				Content: model.ContentVal{Str: ptrStr("")},
				ToolCalls: []model.ToolCall{
					{
						ID:   "call_1",
						Type: "function",
						Function: model.ToolCallFunc{
							Name:      "search_flights",
							Arguments: "{\"origin\": \"NYC\", \"destination\": \"LA\"}",
						},
					},
				},
			},
		},
	}

	estimated := h.estimateInputTokens(req)
	if estimated == 0 {
		t.Errorf("estimateInputTokens with tool calls: got 0, expected > 0")
	}
}

func ptrStr(s string) *string {
	return &s
}
