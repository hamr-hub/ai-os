package proxy

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"go.uber.org/zap"
)

type VLLMProxy struct {
	logger        *zap.Logger
	requestClient *http.Client
	streamClient  *http.Client
	vllmHost      string
	cb            *CircuitBreaker
}

type contextKey string

const requestIDKey contextKey = "request_id"

func ContextWithRequestID(ctx context.Context, requestID string) context.Context {
	return context.WithValue(ctx, requestIDKey, requestID)
}

func requestIDFromContext(ctx context.Context) string {
	if v, ok := ctx.Value(requestIDKey).(string); ok {
		return v
	}
	return ""
}

func attachRequestIDHeader(req *http.Request, ctx context.Context) {
	rid := requestIDFromContext(ctx)
	if rid != "" {
		req.Header.Set("X-Request-ID", rid)
	}
}

func NewVLLMProxy(logger *zap.Logger, vllmHost string) *VLLMProxy {
	if vllmHost == "" {
		vllmHost = "localhost"
	}
	return &VLLMProxy{
		logger:   logger,
		vllmHost: vllmHost,
		cb:       NewCircuitBreaker(5, 30*time.Second),
		requestClient: &http.Client{
			Timeout: 60 * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:        200,
				MaxIdleConnsPerHost: 50,
				IdleConnTimeout:     90 * time.Second,
			},
		},
		streamClient: &http.Client{
			Timeout: 0,
			Transport: &http.Transport{
				MaxIdleConns:          200,
				MaxIdleConnsPerHost:   50,
				IdleConnTimeout:       90 * time.Second,
				ResponseHeaderTimeout: 120 * time.Second,
			},
		},
	}
}

func (p *VLLMProxy) CircuitBreakerStats() map[string]interface{} {
	return p.cb.Stats()
}

func readErrorBody(resp *http.Response) string {
	if resp == nil || resp.Body == nil {
		return ""
	}

	body, err := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if err != nil {
		return ""
	}

	return strings.TrimSpace(string(body))
}

func (p *VLLMProxy) ChatCompletion(ctx context.Context, port int, payload interface{}) (interface{}, error) {
	if !p.cb.Allow() {
		return nil, fmt.Errorf("circuit open: upstream unavailable (last error: %v)", p.cb.LastError())
	}

	url := fmt.Sprintf("http://%s:%d/v1/chat/completions", p.vllmHost, port)
	data, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(data))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := p.requestClient.Do(req)
	if err != nil {
		p.cb.RecordFailure(err)
		return nil, fmt.Errorf("vLLM request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body := readErrorBody(resp)
		errMsg := fmt.Errorf("vLLM returned %d: %s", resp.StatusCode, body)
		p.cb.RecordFailure(errMsg)
		if body == "" {
			return nil, fmt.Errorf("vLLM returned %d", resp.StatusCode)
		}
		return nil, fmt.Errorf("vLLM returned %d: %s", resp.StatusCode, body)
	}

	var result interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		p.cb.RecordFailure(err)
		return nil, err
	}
	p.cb.RecordSuccess()
	return result, nil
}

func (p *VLLMProxy) StreamChatCompletion(ctx context.Context, port int, payload interface{}) (<-chan StreamEvent, error) {
	if !p.cb.Allow() {
		return nil, fmt.Errorf("circuit open: upstream unavailable (last error: %v)", p.cb.LastError())
	}

	url := fmt.Sprintf("http://%s:%d/v1/chat/completions", p.vllmHost, port)
	data, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(data))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "text/event-stream")

	resp, err := p.streamClient.Do(req)
	if err != nil {
		p.cb.RecordFailure(err)
		return nil, fmt.Errorf("vLLM stream request: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		body := readErrorBody(resp)
		resp.Body.Close()
		errMsg := fmt.Errorf("vLLM returned %d: %s", resp.StatusCode, body)
		p.cb.RecordFailure(errMsg)
		if body == "" {
			return nil, fmt.Errorf("vLLM returned %d", resp.StatusCode)
		}
		return nil, fmt.Errorf("vLLM returned %d: %s", resp.StatusCode, body)
	}

	ch := make(chan StreamEvent, 256)
	go p.streamReader(resp, ch)
	return ch, nil
}

type StreamEvent struct {
	Data  string
	Done  bool
	Error error
}

func (p *VLLMProxy) streamReader(resp *http.Response, ch chan<- StreamEvent) {
	defer close(ch)
	defer resp.Body.Close()

	scanner := bufio.NewScanner(resp.Body)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)

	scanResults := make(chan string, 16)
	scanDone := make(chan struct{})

	go func() {
		defer close(scanDone)
		for scanner.Scan() {
			scanResults <- scanner.Text()
		}
	}()

	heartbeatTicker := time.NewTicker(10 * time.Second)
	defer heartbeatTicker.Stop()

	for {
		select {
		case line, ok := <-scanResults:
			if !ok {
				if err := scanner.Err(); err != nil {
					p.logger.Warn("stream reader failed", zap.Error(err))
					ch <- StreamEvent{Error: err}
				}
				return
			}
			heartbeatTicker.Reset(10 * time.Second)
			if strings.HasPrefix(line, "data: ") {
				data := strings.TrimPrefix(line, "data: ")
				if data == "[DONE]" {
					ch <- StreamEvent{Data: "data: [DONE]\n\n", Done: true}
					return
				}
				ch <- StreamEvent{Data: line + "\n\n"}
			}
		case <-heartbeatTicker.C:
			ch <- StreamEvent{Data: ": heartbeat\n\n"}
		case <-scanDone:
			return
		}
	}
}

func (p *VLLMProxy) ListModels(ctx context.Context, port int) (interface{}, error) {
	url := fmt.Sprintf("http://localhost:%d/v1/models", port)
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, err
	}
	resp, err := p.requestClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body := readErrorBody(resp)
		if body == "" {
			return nil, fmt.Errorf("vLLM returned %d", resp.StatusCode)
		}
		return nil, fmt.Errorf("vLLM returned %d: %s", resp.StatusCode, body)
	}

	var result interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}
	return result, nil
}

func (p *VLLMProxy) WaitUntilReady(ctx context.Context, port int, timeout time.Duration, interval time.Duration) error {
	if timeout <= 0 {
		timeout = 600 * time.Second
	}
	if interval <= 0 {
		interval = 5 * time.Second
	}

	deadline := time.Now().Add(timeout)
	var lastErr error
	pollInterval := 2 * time.Second

	for {
		req, err := http.NewRequestWithContext(ctx, "GET", fmt.Sprintf("http://localhost:%d/v1/models", port), nil)
		if err != nil {
			return err
		}

		resp, err := p.requestClient.Do(req)
		if err == nil {
			body, readErr := io.ReadAll(io.LimitReader(resp.Body, 512))
			resp.Body.Close()
			if readErr != nil {
				lastErr = fmt.Errorf("read readiness response: %w", readErr)
			} else if resp.StatusCode == http.StatusOK {
				return nil
			} else {
				lastErr = fmt.Errorf("readiness returned %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
			}
		} else {
			lastErr = fmt.Errorf("readiness probe failed: %w", err)
		}

		if time.Now().After(deadline) {
			if lastErr == nil {
				lastErr = fmt.Errorf("readiness probe timed out")
			}
			return lastErr
		}

		timer := time.NewTimer(pollInterval)
		select {
		case <-ctx.Done():
			timer.Stop()
			return ctx.Err()
		case <-timer.C:
		}
		pollInterval = time.Duration(float64(pollInterval) * 1.5)
		if pollInterval > interval {
			pollInterval = interval
		}
	}
}

func (p *VLLMProxy) Embeddings(ctx context.Context, port int, payload interface{}) (interface{}, error) {
	if !p.cb.Allow() {
		return nil, fmt.Errorf("circuit open: upstream unavailable (last error: %v)", p.cb.LastError())
	}

	url := fmt.Sprintf("http://localhost:%d/v1/embeddings", port)
	data, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(data))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := p.requestClient.Do(req)
	if err != nil {
		p.cb.RecordFailure(err)
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body := readErrorBody(resp)
		errMsg := fmt.Errorf("vLLM returned %d: %s", resp.StatusCode, body)
		p.cb.RecordFailure(errMsg)
		if body == "" {
			return nil, fmt.Errorf("vLLM returned %d", resp.StatusCode)
		}
		return nil, fmt.Errorf("vLLM returned %d: %s", resp.StatusCode, body)
	}

	var result interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		p.cb.RecordFailure(err)
		return nil, err
	}
	p.cb.RecordSuccess()
	return result, nil
}

func (p *VLLMProxy) PostEndpoint(ctx context.Context, port int, path string, payload interface{}) (interface{}, error) {
	url := fmt.Sprintf("http://localhost:%d/%s", port, path)
	data, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(data))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := p.requestClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body := readErrorBody(resp)
		if body == "" {
			return nil, fmt.Errorf("vLLM returned %d", resp.StatusCode)
		}
		return nil, fmt.Errorf("vLLM returned %d: %s", resp.StatusCode, body)
	}

	var result interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}
	return result, nil
}
