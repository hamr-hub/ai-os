package service

import (
	"context"
	"fmt"
	"time"

	"go-vllm-api/internal/repository"

	"go.uber.org/zap"
)

type RateLimiter struct {
	redis  *repository.RedisRepo
	logger *zap.Logger
	prefix string
}

var Priorities = map[string]int{"low": 1, "normal": 2, "high": 3, "critical": 4}

func NewRateLimiter(redis *repository.RedisRepo, logger *zap.Logger) *RateLimiter {
	return &RateLimiter{
		redis:  redis,
		logger: logger,
		prefix: "ai_controller:",
	}
}

func (rl *RateLimiter) activeKey(model string) string {
	return fmt.Sprintf("%sactive_requests:%s", rl.prefix, model)
}

func (rl *RateLimiter) AcquireRequest(model string, maxConcurrent int) bool {
	if rl.redis == nil || !rl.redis.IsConnected() {
		return true
	}
	ctx := context.Background()
	key := rl.activeKey(model)
	current, _ := rl.redis.Incr(ctx, key)
	if current > int64(maxConcurrent) {
		rl.redis.Decr(ctx, key)
		return false
	}
	rl.redis.Expire(ctx, key, 60*time.Second)
	return true
}

func (rl *RateLimiter) ReleaseRequest(model string) {
	if rl.redis == nil || !rl.redis.IsConnected() {
		return
	}
	ctx := context.Background()
	key := rl.activeKey(model)
	val, _ := rl.redis.Decr(ctx, key)
	if val < 0 {
		rl.redis.Incr(ctx, key)
	}
}

func (rl *RateLimiter) GetActiveRequests(model string) int {
	if rl.redis == nil || !rl.redis.IsConnected() {
		return 0
	}
	ctx := context.Background()
	key := rl.activeKey(model)
	val, err := rl.redis.Get(ctx, key)
	if err != nil || val == "" {
		return 0
	}
	var n int
	fmt.Sscanf(val, "%d", &n)
	return n
}

func (rl *RateLimiter) CanAcceptRequest(model string, maxConcurrent int) bool {
	return rl.GetActiveRequests(model) < maxConcurrent
}

func (rl *RateLimiter) GetTotalQueueLength(model string) int {
	if rl.redis == nil || !rl.redis.IsConnected() {
		return 0
	}
	ctx := context.Background()
	total := 0
	for _, level := range Priorities {
		key := fmt.Sprintf("%squeue:%s:%d", rl.prefix, model, level)
		val, err := rl.redis.Get(ctx, key)
		if err == nil && val != "" {
			n, _ := fmt.Sscanf(val, "%d", new(int))
			_ = n
		}
		_ = key
	}
	return total
}

func (rl *RateLimiter) CanAcceptClientRequest(clientID string, maxConcurrent int) bool {
	if rl.redis == nil || !rl.redis.IsConnected() {
		return true
	}
	ctx := context.Background()
	key := fmt.Sprintf("%srate_limit:%s", rl.prefix, clientID)
	current, _ := rl.redis.Incr(ctx, key)
	if current > int64(maxConcurrent) {
		rl.redis.Decr(ctx, key)
		return false
	}
	rl.redis.Expire(ctx, key, 60*time.Second)
	return true
}

func (rl *RateLimiter) GetClientRequestCount(clientID string) int {
	if rl.redis == nil || !rl.redis.IsConnected() {
		return 0
	}
	ctx := context.Background()
	key := fmt.Sprintf("%srate_limit:%s", rl.prefix, clientID)
	val, err := rl.redis.Get(ctx, key)
	if err != nil || val == "" {
		return 0
	}
	var n int
	fmt.Sscanf(val, "%d", &n)
	return n
}

func (rl *RateLimiter) WaitForSlot(ctx context.Context, model string, maxConcurrent int, timeout time.Duration) bool {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if rl.CanAcceptRequest(model, maxConcurrent) {
			return true
		}
		select {
		case <-ctx.Done():
			return false
		case <-time.After(500 * time.Millisecond):
		}
	}
	return false
}

func (rl *RateLimiter) Flush() {
	if rl.redis == nil || !rl.redis.IsConnected() {
		return
	}
	ctx := context.Background()
	rl.redis.Delete(ctx, rl.prefix+"active_requests:*")
}
