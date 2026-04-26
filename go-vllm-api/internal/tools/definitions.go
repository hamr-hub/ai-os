package tools

import (
	"encoding/json"
)

type ParameterType string

const (
	TypeString  ParameterType = "string"
	TypeNumber  ParameterType = "number"
	TypeInteger ParameterType = "integer"
	TypeBoolean ParameterType = "boolean"
	TypeArray   ParameterType = "array"
	TypeObject  ParameterType = "object"
)

type ToolParameter struct {
	Name        string           `json:"name"`
	Type        ParameterType    `json:"type"`
	Description string           `json:"description"`
	Required    bool             `json:"required"`
	Default     any              `json:"default,omitempty"`
	Enum        []string         `json:"enum,omitempty"`
	MinValue    *float64         `json:"minimum,omitempty"`
	MaxValue    *float64         `json:"maximum,omitempty"`
	Items       *json.RawMessage `json:"items,omitempty"`
}

func (p *ToolParameter) ToJSONSchema() map[string]any {
	schema := map[string]any{
		"type":        string(p.Type),
		"description": p.Description,
	}

	if len(p.Enum) > 0 {
		schema["enum"] = p.Enum
	}

	if p.Type == TypeNumber || p.Type == TypeInteger {
		if p.MinValue != nil {
			schema["minimum"] = *p.MinValue
		}
		if p.MaxValue != nil {
			schema["maximum"] = *p.MaxValue
		}
	}

	if p.Type == TypeArray && p.Items != nil {
		schema["items"] = *p.Items
	}

	return schema
}

type ToolDefinition struct {
	Name                 string           `json:"name"`
	Description          string           `json:"description"`
	Parameters           []ToolParameter  `json:"parameters"`
	Category             string           `json:"category"`
	Examples             []map[string]any `json:"examples,omitempty"`
	Dangerous            bool             `json:"dangerous"`
	RequiresConfirmation bool             `json:"requires_confirmation"`
}

func (t *ToolDefinition) ToOpenAIFunction() map[string]any {
	properties := make(map[string]any)
	required := make([]string, 0)

	for _, param := range t.Parameters {
		properties[param.Name] = param.ToJSONSchema()
		if param.Required {
			required = append(required, param.Name)
		}
	}

	return map[string]any{
		"type": "function",
		"function": map[string]any{
			"name":        t.Name,
			"description": t.Description,
			"parameters": map[string]any{
				"type":       "object",
				"properties": properties,
				"required":   required,
			},
		},
	}
}
