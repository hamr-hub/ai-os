package proxy

import (
	"fmt"
	"sync"
	"time"
)

type CircuitState int

const (
	StateClosed   CircuitState = iota
	StateOpen
	StateHalfOpen
)

func (s CircuitState) String() string {
	switch s {
	case StateClosed:
		return "closed"
	case StateOpen:
		return "open"
	case StateHalfOpen:
		return "half_open"
	default:
		return "unknown"
	}
}

type CircuitBreaker struct {
	mu               sync.RWMutex
	state            CircuitState
	failureCount     int
	failureThreshold int
	successThreshold int
	successCount     int
	openedAt         time.Time
	resetTimeout     time.Duration
	lastError        error
	totalFailures    int64
	totalSuccesses   int64
	stateTransitions int64
}

func NewCircuitBreaker(failureThreshold int, resetTimeout time.Duration) *CircuitBreaker {
	if failureThreshold <= 0 {
		failureThreshold = 5
	}
	if resetTimeout <= 0 {
		resetTimeout = 30 * time.Second
	}
	return &CircuitBreaker{
		failureThreshold: failureThreshold,
		successThreshold: 2,
		resetTimeout:     resetTimeout,
		state:            StateClosed,
	}
}

func (cb *CircuitBreaker) Allow() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	switch cb.state {
	case StateClosed:
		return true
	case StateOpen:
		if time.Since(cb.openedAt) > cb.resetTimeout {
			cb.state = StateHalfOpen
			cb.successCount = 0
			cb.stateTransitions++
			return true
		}
		return false
	case StateHalfOpen:
		return true
	default:
		return false
	}
}

func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.totalSuccesses++

	switch cb.state {
	case StateHalfOpen:
		cb.successCount++
		if cb.successCount >= cb.successThreshold {
			cb.state = StateClosed
			cb.failureCount = 0
			cb.stateTransitions++
		}
	case StateClosed:
		cb.failureCount = 0
	}
}

func (cb *CircuitBreaker) RecordFailure(err error) {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.totalFailures++
	cb.lastError = err

	switch cb.state {
	case StateClosed:
		cb.failureCount++
		if cb.failureCount >= cb.failureThreshold {
			cb.state = StateOpen
			cb.openedAt = time.Now()
			cb.stateTransitions++
		}
	case StateHalfOpen:
		cb.state = StateOpen
		cb.openedAt = time.Now()
		cb.failureCount = cb.failureThreshold
		cb.stateTransitions++
	}
}

func (cb *CircuitBreaker) State() CircuitState {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.state
}

func (cb *CircuitBreaker) LastError() error {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.lastError
}

func (cb *CircuitBreaker) Stats() map[string]interface{} {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return map[string]interface{}{
		"state":            cb.state.String(),
		"failure_count":    cb.failureCount,
		"failure_threshold": cb.failureThreshold,
		"success_threshold": cb.successThreshold,
		"success_count":    cb.successCount,
		"opened_at":        cb.openedAt.Format(time.RFC3339),
		"reset_timeout":    cb.resetTimeout.String(),
		"last_error":       fmt.Sprintf("%v", cb.lastError),
		"total_failures":   cb.totalFailures,
		"total_successes":  cb.totalSuccesses,
		"state_transitions": cb.stateTransitions,
	}
}
