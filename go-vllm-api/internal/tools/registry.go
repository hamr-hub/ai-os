package tools

import "sync"

type ToolRegistry struct {
	mu         sync.RWMutex
	tools      map[string]*ToolDefinition
	categories map[string][]string
}

var (
	registryInstance *ToolRegistry
	registryOnce     sync.Once
)

func GetRegistry() *ToolRegistry {
	registryOnce.Do(func() {
		registryInstance = &ToolRegistry{
			tools:      make(map[string]*ToolDefinition),
			categories: make(map[string][]string),
		}
		registryInstance.registerBuiltinTools()
	})
	return registryInstance
}

func (r *ToolRegistry) registerBuiltinTools() {
	r.Register(&ToolDefinition{
		Name:        "get_system_info",
		Description: "Get current system information including CPU, memory, and GPU status",
		Parameters:  []ToolParameter{},
		Category:    "system",
		Dangerous:   false,
	})

	r.Register(&ToolDefinition{
		Name:        "list_models",
		Description: "List all available models and their status",
		Parameters:  []ToolParameter{},
		Category:    "models",
		Dangerous:   false,
	})

	minVal := 1.0
	maxVal := 100.0
	r.Register(&ToolDefinition{
		Name:        "start_model",
		Description: "Start a specific model by name",
		Parameters: []ToolParameter{
			{
				Name:        "model_name",
				Type:        TypeString,
				Description: "Name of the model to start",
				Required:    true,
			},
		},
		Category:             "models",
		Dangerous:            true,
		RequiresConfirmation: true,
	})

	r.Register(&ToolDefinition{
		Name:        "stop_model",
		Description: "Stop a specific model by name",
		Parameters: []ToolParameter{
			{
				Name:        "model_name",
				Type:        TypeString,
				Description: "Name of the model to stop",
				Required:    true,
			},
		},
		Category:             "models",
		Dangerous:            true,
		RequiresConfirmation: true,
	})

	r.Register(&ToolDefinition{
		Name:        "switch_model",
		Description: "Switch to a specific model, stopping others if necessary",
		Parameters: []ToolParameter{
			{
				Name:        "model_name",
				Type:        TypeString,
				Description: "Name of the model to switch to",
				Required:    true,
			},
		},
		Category:             "models",
		Dangerous:            true,
		RequiresConfirmation: true,
	})

	r.Register(&ToolDefinition{
		Name:        "get_gpu_status",
		Description: "Get detailed GPU status including memory usage and temperature",
		Parameters:  []ToolParameter{},
		Category:    "gpu",
		Dangerous:   false,
	})

	r.Register(&ToolDefinition{
		Name:        "optimize_gpu_memory",
		Description: "Optimize GPU memory usage by clearing cache and adjusting parameters",
		Parameters: []ToolParameter{
			{
				Name:        "strategy",
				Type:        TypeString,
				Description: "Optimization strategy to use",
				Enum:        []string{"conservative", "balanced", "aggressive"},
				Default:     "balanced",
				Required:    false,
			},
		},
		Category:             "gpu",
		Dangerous:            true,
		RequiresConfirmation: true,
	})

	r.Register(&ToolDefinition{
		Name:        "search_conversations",
		Description: "Search through conversation history",
		Parameters: []ToolParameter{
			{
				Name:        "query",
				Type:        TypeString,
				Description: "Search query",
				Required:    true,
			},
			{
				Name:        "limit",
				Type:        TypeInteger,
				Description: "Maximum number of results to return",
				Default:     10.0,
				MinValue:    &minVal,
				MaxValue:    &maxVal,
				Required:    false,
			},
		},
		Category:  "chat",
		Dangerous: false,
	})

	r.Register(&ToolDefinition{
		Name:        "read_file",
		Description: "Read content from a file in the workspace",
		Parameters: []ToolParameter{
			{
				Name:        "file_path",
				Type:        TypeString,
				Description: "Path to the file to read",
				Required:    true,
			},
		},
		Category:  "files",
		Dangerous: false,
	})

	r.Register(&ToolDefinition{
		Name:        "write_file",
		Description: "Write content to a file in the workspace",
		Parameters: []ToolParameter{
			{
				Name:        "file_path",
				Type:        TypeString,
				Description: "Path to the file to write",
				Required:    true,
			},
			{
				Name:        "content",
				Type:        TypeString,
				Description: "Content to write to the file",
				Required:    true,
			},
		},
		Category:             "files",
		Dangerous:            true,
		RequiresConfirmation: true,
	})

	numResults := 5.0
	maxResults := 20.0
	minResults := 1.0
	r.Register(&ToolDefinition{
		Name:        "web_search",
		Description: "Search the web for information",
		Parameters: []ToolParameter{
			{
				Name:        "query",
				Type:        TypeString,
				Description: "Search query",
				Required:    true,
			},
			{
				Name:        "num_results",
				Type:        TypeInteger,
				Description: "Number of results to return",
				Default:     numResults,
				MinValue:    &minResults,
				MaxValue:    &maxResults,
				Required:    false,
			},
		},
		Category:  "web",
		Dangerous: false,
	})
}

func (r *ToolRegistry) Register(tool *ToolDefinition) {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.tools[tool.Name] = tool

	if _, exists := r.categories[tool.Category]; !exists {
		r.categories[tool.Category] = []string{}
	}
	r.categories[tool.Category] = append(r.categories[tool.Category], tool.Name)
}

func (r *ToolRegistry) Unregister(name string) bool {
	r.mu.Lock()
	defer r.mu.Unlock()

	tool, exists := r.tools[name]
	if !exists {
		return false
	}

	if cats, catExists := r.categories[tool.Category]; catExists {
		for i, toolName := range cats {
			if toolName == name {
				r.categories[tool.Category] = append(cats[:i], cats[i+1:]...)
				break
			}
		}
	}

	delete(r.tools, name)
	return true
}

func (r *ToolRegistry) Get(name string) *ToolDefinition {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.tools[name]
}

func (r *ToolRegistry) GetAll() []*ToolDefinition {
	r.mu.RLock()
	defer r.mu.RUnlock()

	tools := make([]*ToolDefinition, 0, len(r.tools))
	for _, tool := range r.tools {
		tools = append(tools, tool)
	}
	return tools
}

func (r *ToolRegistry) GetByCategory(category string) []*ToolDefinition {
	r.mu.RLock()
	defer r.mu.RUnlock()

	toolNames, exists := r.categories[category]
	if !exists {
		return []*ToolDefinition{}
	}

	tools := make([]*ToolDefinition, 0, len(toolNames))
	for _, name := range toolNames {
		if tool, exists := r.tools[name]; exists {
			tools = append(tools, tool)
		}
	}
	return tools
}

func (r *ToolRegistry) GetOpenAITools(categories []string) []map[string]any {
	var tools []*ToolDefinition

	if len(categories) > 0 {
		for _, cat := range categories {
			tools = append(tools, r.GetByCategory(cat)...)
		}
	} else {
		tools = r.GetAll()
	}

	result := make([]map[string]any, 0, len(tools))
	for _, tool := range tools {
		result = append(result, tool.ToOpenAIFunction())
	}
	return result
}

func (r *ToolRegistry) GetCategories() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()

	categories := make([]string, 0, len(r.categories))
	for cat := range r.categories {
		categories = append(categories, cat)
	}
	return categories
}

func (r *ToolRegistry) ToolExists(name string) bool {
	r.mu.RLock()
	defer r.mu.RUnlock()
	_, exists := r.tools[name]
	return exists
}

func (r *ToolRegistry) IsDangerous(name string) bool {
	tool := r.Get(name)
	return tool != nil && tool.Dangerous
}

func (r *ToolRegistry) RequiresConfirmation(name string) bool {
	tool := r.Get(name)
	return tool != nil && tool.RequiresConfirmation
}
