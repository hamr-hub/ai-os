package repository

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

type RedisRepo struct {
	client *redis.Client
	logger *zap.Logger
	stats  CacheStats
}

type CacheStats struct {
	Hits    int64 `json:"hits"`
	Misses  int64 `json:"misses"`
	Sets    int64 `json:"sets"`
	Deletes int64 `json:"deletes"`
}

func NewRedisRepo(host string, port int, db int, logger *zap.Logger) *RedisRepo {
	r := &RedisRepo{
		logger: logger,
	}
	r.client = redis.NewClient(&redis.Options{
		Addr:         fmt.Sprintf("%s:%d", host, port),
		DB:           db,
		DialTimeout:  5 * time.Second,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 5 * time.Second,
		PoolSize:     20,
	})
	return r
}

func (r *RedisRepo) Connect() error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := r.client.Ping(ctx).Err(); err != nil {
		r.client = nil
		return fmt.Errorf("redis connect: %w", err)
	}
	r.logger.Info("redis connected")
	return nil
}

func (r *RedisRepo) IsConnected() bool {
	if r.client == nil {
		return false
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	return r.client.Ping(ctx).Err() == nil
}

func (r *RedisRepo) Close() error {
	if r.client != nil {
		return r.client.Close()
	}
	return nil
}

func (r *RedisRepo) Get(ctx context.Context, key string) (string, error) {
	if r.client == nil {
		return "", fmt.Errorf("redis not connected")
	}
	val, err := r.client.Get(ctx, key).Result()
	if err == redis.Nil {
		r.stats.Misses++
		return "", nil
	}
	if err != nil {
		return "", err
	}
	r.stats.Hits++
	return val, nil
}

func (r *RedisRepo) Set(ctx context.Context, key string, value string, expire time.Duration) error {
	if r.client == nil {
		return fmt.Errorf("redis not connected")
	}
	err := r.client.Set(ctx, key, value, expire).Err()
	if err == nil {
		r.stats.Sets++
	}
	return err
}

func (r *RedisRepo) GetJSON(ctx context.Context, key string) (interface{}, error) {
	val, err := r.Get(ctx, key)
	if err != nil || val == "" {
		return nil, err
	}
	var result interface{}
	if err := json.Unmarshal([]byte(val), &result); err != nil {
		return nil, err
	}
	return result, nil
}

func (r *RedisRepo) SetJSON(ctx context.Context, key string, value interface{}, expire time.Duration) error {
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return r.Set(ctx, key, string(data), expire)
}

func (r *RedisRepo) Delete(ctx context.Context, key string) error {
	if r.client == nil {
		return fmt.Errorf("redis not connected")
	}
	err := r.client.Del(ctx, key).Err()
	if err == nil {
		r.stats.Deletes++
	}
	return err
}

func (r *RedisRepo) Exists(ctx context.Context, key string) (bool, error) {
	if r.client == nil {
		return false, fmt.Errorf("redis not connected")
	}
	n, err := r.client.Exists(ctx, key).Result()
	return n > 0, err
}

func (r *RedisRepo) Keys(ctx context.Context, pattern string) ([]string, error) {
	if r.client == nil {
		return nil, fmt.Errorf("redis not connected")
	}
	return r.client.Keys(ctx, pattern).Result()
}

func (r *RedisRepo) FlushDB(ctx context.Context) error {
	if r.client == nil {
		return fmt.Errorf("redis not connected")
	}
	return r.client.FlushDB(ctx).Err()
}

func (r *RedisRepo) Incr(ctx context.Context, key string) (int64, error) {
	if r.client == nil {
		return 0, fmt.Errorf("redis not connected")
	}
	return r.client.Incr(ctx, key).Result()
}

func (r *RedisRepo) Decr(ctx context.Context, key string) (int64, error) {
	if r.client == nil {
		return 0, fmt.Errorf("redis not connected")
	}
	return r.client.Decr(ctx, key).Result()
}

func (r *RedisRepo) LPush(ctx context.Context, key string, values ...interface{}) error {
	if r.client == nil {
		return fmt.Errorf("redis not connected")
	}
	return r.client.LPush(ctx, key, values...).Err()
}

func (r *RedisRepo) LRange(ctx context.Context, key string, start, stop int64) ([]string, error) {
	if r.client == nil {
		return nil, fmt.Errorf("redis not connected")
	}
	return r.client.LRange(ctx, key, start, stop).Result()
}

func (r *RedisRepo) LTrim(ctx context.Context, key string, start, stop int64) error {
	if r.client == nil {
		return fmt.Errorf("redis not connected")
	}
	return r.client.LTrim(ctx, key, start, stop).Err()
}

func (r *RedisRepo) Expire(ctx context.Context, key string, ttl time.Duration) error {
	if r.client == nil {
		return fmt.Errorf("redis not connected")
	}
	return r.client.Expire(ctx, key, ttl).Err()
}

func (r *RedisRepo) HSet(ctx context.Context, key string, values ...interface{}) error {
	if r.client == nil {
		return fmt.Errorf("redis not connected")
	}
	return r.client.HSet(ctx, key, values...).Err()
}

func (r *RedisRepo) HGetAll(ctx context.Context, key string) (map[string]string, error) {
	if r.client == nil {
		return nil, fmt.Errorf("redis not connected")
	}
	return r.client.HGetAll(ctx, key).Result()
}

func (r *RedisRepo) SAdd(ctx context.Context, key string, members ...interface{}) error {
	if r.client == nil {
		return fmt.Errorf("redis not connected")
	}
	return r.client.SAdd(ctx, key, members...).Err()
}

func (r *RedisRepo) SMembers(ctx context.Context, key string) ([]string, error) {
	if r.client == nil {
		return nil, fmt.Errorf("redis not connected")
	}
	return r.client.SMembers(ctx, key).Result()
}

func (r *RedisRepo) TxPipeline(ctx context.Context) redis.Pipeliner {
	return r.client.TxPipeline()
}

func (r *RedisRepo) Pipeline(ctx context.Context) redis.Pipeliner {
	return r.client.Pipeline()
}

func (r *RedisRepo) Watch(ctx context.Context, keys ...string) error {
	return r.client.Watch(ctx, func(tx *redis.Tx) error {
		return nil
	}, keys...)
}

func (r *RedisRepo) GetStats() CacheStats {
	return r.stats
}

func (r *RedisRepo) Info(ctx context.Context, section ...string) (map[string]map[string]string, error) {
	if r.client == nil {
		return nil, fmt.Errorf("redis not connected")
	}
	return r.client.InfoMap(ctx, section...).Result()
}
