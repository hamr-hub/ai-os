package service

import (
	"context"
	"sync"
	"time"

	"go-vllm-api/internal/repository"
)

type cacheEntry struct {
	value     interface{}
	expiredAt time.Time
}

type CacheService struct {
	redis *repository.RedisRepo
	local map[string]cacheEntry
	mu    sync.RWMutex
	stats CacheStats
}

type CacheStats struct {
	Hits   int64 `json:"hits"`
	Misses int64 `json:"misses"`
	Sets   int64 `json:"sets"`
	Deletes int64 `json:"deletes"`
	LocalSize int `json:"local_size"`
}

func NewCacheService(redis *repository.RedisRepo) *CacheService {
	return &CacheService{
		redis: redis,
		local: make(map[string]cacheEntry),
	}
}

func (cs *CacheService) Get(key string) interface{} {
	cs.mu.RLock()
	if entry, ok := cs.local[key]; ok {
		if time.Now().Before(entry.expiredAt) {
			cs.mu.RUnlock()
			cs.stats.Hits++
			return entry.value
		}
		cs.mu.RUnlock()
		cs.mu.Lock()
		delete(cs.local, key)
		cs.mu.Unlock()
	} else {
		cs.mu.RUnlock()
	}

	if cs.redis != nil && cs.redis.IsConnected() {
		ctx := context.Background()
		val, err := cs.redis.GetJSON(ctx, key)
		if err == nil && val != nil {
			cs.stats.Hits++
			return val
		}
	}

	cs.stats.Misses++
	return nil
}

func (cs *CacheService) Set(key string, value interface{}, ttlSeconds int) {
	cs.mu.Lock()
	cs.local[key] = cacheEntry{
		value:     value,
		expiredAt: time.Now().Add(time.Duration(ttlSeconds) * time.Second),
	}
	cs.mu.Unlock()
	cs.stats.Sets++

	if cs.redis != nil && cs.redis.IsConnected() {
		ctx := context.Background()
		ttl := time.Duration(ttlSeconds) * time.Second
		if err := cs.redis.SetJSON(ctx, key, value, ttl); err != nil {
		}
	}
}

func (cs *CacheService) Delete(key string) {
	cs.mu.Lock()
	delete(cs.local, key)
	cs.mu.Unlock()
	cs.stats.Deletes++

	if cs.redis != nil && cs.redis.IsConnected() {
		ctx := context.Background()
		cs.redis.Delete(ctx, key)
	}
}

func (cs *CacheService) FlushAll() {
	cs.mu.Lock()
	cs.local = make(map[string]cacheEntry)
	cs.mu.Unlock()
}

func (cs *CacheService) GetStats() CacheStats {
	cs.mu.RLock()
	defer cs.mu.RUnlock()
	cs.stats.LocalSize = len(cs.local)
	return cs.stats
}
