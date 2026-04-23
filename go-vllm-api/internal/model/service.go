package model

type ServiceControlRequest struct {
	ServiceName string `json:"service_name,omitempty"`
}

type APIStatus struct {
	Status          string                   `json:"status"`
	Timestamp       string                   `json:"timestamp"`
	GPUAvailable    bool                     `json:"gpu_available"`
	AvailableModels int                      `json:"available_models"`
	RunningModels   int                      `json:"running_models"`
	Models          []map[string]interface{} `json:"models"`
}

type ErrorResponse struct {
	Error      string `json:"error"`
	Code       int    `json:"code"`
	Timestamp  string `json:"timestamp"`
	Path       string `json:"path"`
}
