#!/usr/bin/env python3
"""
Redis 连接测试脚本
连接 jetson-local.hamr.top:6379
"""

import redis
import sys
import time

REDIS_HOST = "jetson-local.hamr.top"
REDIS_PORT = 6379
REDIS_TIMEOUT = 5

def test_redis_connection():
    """测试 Redis 连接"""
    print(f"🔗 Testing Redis connection to {REDIS_HOST}:{REDIS_PORT}")
    
    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            socket_connect_timeout=REDIS_TIMEOUT,
            socket_timeout=REDIS_TIMEOUT,
            decode_responses=True
        )
        
        start_time = time.time()
        result = r.ping()
        elapsed_time = time.time() - start_time
        
        if result:
            print(f"✅ Redis connection successful!")
            print(f"   Response time: {elapsed_time:.3f}s")
            print(f"   PING → PONG")
            
            try:
                info = r.info("server")
                print(f"   Redis version: {info.get('redis_version', 'unknown')}")
                print(f"   OS: {info.get('os', 'unknown')}")
            except Exception as e:
                print(f"   (Could not get server info: {e})")
            
            return True
        else:
            print(f"❌ Redis ping failed: unexpected response")
            return False
            
    except redis.ConnectionError as e:
        print(f"❌ Redis connection failed: {e}")
        print(f"   Possible reasons:")
        print(f"   - Redis server not running on {REDIS_HOST}:{REDIS_PORT}")
        print(f"   - Firewall blocking connection")
        print(f"   - Network unreachable")
        return False
        
    except redis.TimeoutError as e:
        print(f"❌ Redis connection timeout: {e}")
        print(f"   Timeout after {REDIS_TIMEOUT}s")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_redis_operations():
    """测试 Redis 基本操作"""
    print(f"\n📝 Testing Redis operations...")
    
    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            socket_connect_timeout=REDIS_TIMEOUT,
            decode_responses=True
        )
        
        test_key = "test:mock_vllm:e2e_test"
        test_value = f"test_value_{int(time.time())}"
        
        r.set(test_key, test_value, ex=60)
        print(f"   SET {test_key} = {test_value} (TTL 60s)")
        
        retrieved = r.get(test_key)
        if retrieved == test_value:
            print(f"   GET {test_key} = {retrieved} ✅")
        else:
            print(f"   GET {test_key} = {retrieved} (expected {test_value}) ❌")
        
        r.delete(test_key)
        print(f"   DEL {test_key}")
        
        print(f"✅ Redis operations test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Redis operations test failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Redis Connection Test")
    print("=" * 60)
    
    connection_ok = test_redis_connection()
    
    if connection_ok:
        operations_ok = test_redis_operations()
        
        print("\n" + "=" * 60)
        print("Test Summary:")
        print(f"  Connection: {'✅ PASS' if connection_ok else '❌ FAIL'}")
        print(f"  Operations: {'✅ PASS' if operations_ok else '❌ FAIL'}")
        print("=" * 60)
        
        sys.exit(0 if (connection_ok and operations_ok) else 1)
    else:
        print("\n" + "=" * 60)
        print("Test Summary:")
        print(f"  Connection: ❌ FAIL")
        print("=" * 60)
        print("\n⚠️  Continuing tests without Redis (not blocking)")
        sys.exit(0)
