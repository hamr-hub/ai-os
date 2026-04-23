package model

import (
	"encoding/json"
)

type ChatCompletionRequest struct {
	Model            string            `json:"model"`
	Messages         []ChatMessage     `json:"messages"`
	Stream           bool              `json:"stream,omitempty"`
	MaxTokens        *int              `json:"max_tokens,omitempty"`
	Temperature      *float64          `json:"temperature,omitempty"`
	TopP             *float64          `json:"top_p,omitempty"`
	Stop             []string          `json:"stop,omitempty"`
	PresencePenalty  *float64          `json:"presence_penalty,omitempty"`
	FrequencyPenalty *float64          `json:"frequency_penalty,omitempty"`
	Logprobs         *bool             `json:"logprobs,omitempty"`
	TopLogprobs      *int              `json:"top_logprobs,omitempty"`
	Tools            []ToolDefinition  `json:"tools,omitempty"`
	ToolChoice       interface{}       `json:"tool_choice,omitempty"`
	ResponseFormat   *ResponseFormat   `json:"response_format,omitempty"`
	Seed             *int64            `json:"seed,omitempty"`
	User             string            `json:"user,omitempty"`
}

type ChatMessage struct {
	Role       string     `json:"role"`
	Content    ContentVal `json:"content"`
	Name       string     `json:"name,omitempty"`
	ToolCalls  []ToolCall `json:"tool_calls,omitempty"`
	ToolCallID string     `json:"tool_call_id,omitempty"`
}

type ContentVal struct {
	Str  *string
	List []ContentPart
}

func (cv ContentVal) MarshalJSON() ([]byte, error) {
	if cv.Str != nil {
		return json.Marshal(*cv.Str)
	}
	return json.Marshal(cv.List)
}

func (cv *ContentVal) UnmarshalJSON(data []byte) error {
	var s string
	if err := json.Unmarshal(data, &s); err == nil {
		cv.Str = &s
		cv.List = nil
		return nil
	}
	cv.Str = nil
	return json.Unmarshal(data, &cv.List)
}

type ContentPart struct {
	Type     string        `json:"type"`
	Text     string        `json:"text,omitempty"`
	ImageURL *ImageURLPart `json:"image_url,omitempty"`
}

type ImageURLPart struct {
	URL    string `json:"url"`
	Detail string `json:"detail,omitempty"`
}

type ToolDefinition struct {
	Type     string       `json:"type"`
	Function ToolFunction `json:"function"`
}

type ToolFunction struct {
	Name        string      `json:"name"`
	Description string      `json:"description,omitempty"`
	Parameters  interface{} `json:"parameters,omitempty"`
}

type ToolCall struct {
	ID       string       `json:"id"`
	Type     string       `json:"type"`
	Function ToolCallFunc `json:"function"`
}

type ToolCallFunc struct {
	Name      string `json:"name"`
	Arguments string `json:"arguments"`
}

type ResponseFormat struct {
	Type string `json:"type"`
}

type ChatCompletionResponse struct {
	ID      string                        `json:"id"`
	Object  string                        `json:"object"`
	Created int64                         `json:"created"`
	Model   string                        `json:"model"`
	Choices []ChatCompletionResponseChoice `json:"choices"`
	Usage   *UsageInfo                    `json:"usage,omitempty"`
}

type ChatCompletionResponseChoice struct {
	Index        int                    `json:"index"`
	Message      map[string]interface{} `json:"message"`
	FinishReason string                 `json:"finish_reason"`
	Logprobs     *LogprobsResult        `json:"logprobs,omitempty"`
}

type LogprobsResult struct {
	Content []LogprobToken `json:"content,omitempty"`
}

type LogprobToken struct {
	Token   string  `json:"token"`
	Logprob float64 `json:"logprob"`
	Bytes   []byte  `json:"bytes,omitempty"`
}

type UsageInfo struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

type ChatCompletionChunk struct {
	ID      string                   `json:"id"`
	Object  string                   `json:"object"`
	Created int64                    `json:"created"`
	Model   string                   `json:"model"`
	Choices []map[string]interface{} `json:"choices"`
}

type ModelInfo struct {
	ID             string `json:"id"`
	Object         string `json:"object"`
	Created        int64  `json:"created"`
	OwnedBy        string `json:"owned_by"`
	Running        bool   `json:"running"`
	SupportsImages bool   `json:"supports_images"`
	Description    string `json:"description"`
	Service        string `json:"service"`
	Port           int    `json:"port"`
}

type ModelsListResponse struct {
	Object string      `json:"object"`
	Data   []ModelInfo `json:"data"`
}
