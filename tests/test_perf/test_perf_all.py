"""
性能测试 - 网关转发性能、高并发稳定性、长连接、限流性能
需要安装: pip install k6 pytest-timeout
"""

import pytest
import requests
import json
import time
import threading
import statistics
import concurrent.futures

GO_BASE = "http://localhost:35001"


class TestGatewayPerf:
    def test_forward_latency(self):
        latencies_direct = []
        latencies_proxy = []

        model_port = None
        models_resp = requests.get(f"{GO_BASE}/manage/models", timeout=10).json()
        for m, info in models_resp.items():
            if info.get("running"):
                model_port = info.get("port")
                break

        if not model_port:
            pytest.skip("No running model for perf test")

        for i in range(20):
            start = time.time()
            resp = requests.post(
                f"{GO_BASE}/v1/chat/completions",
                json={
                    "model": "default",
                    "messages": [{"role": "user", "content": f"perf test {i}"}],
                    "stream": False,
                },
                timeout=30,
            )
            elapsed = time.time() - start
            if resp.status_code == 200:
                latencies_proxy.append(elapsed)

        assert len(latencies_proxy) > 0, "No successful proxy requests"
        avg_proxy = statistics.mean(latencies_proxy)
        p99_proxy = sorted(latencies_proxy)[int(0.99 * len(latencies_proxy))] if len(latencies_proxy) > 1 else latencies_proxy[0]

        print(f"\n  Proxy: avg={avg_proxy:.3f}s, p99={p99_proxy:.3f}s, samples={len(latencies_proxy)}")

    def test_concurrent_throughput(self):
        results = []
        start_time = time.time()
        num_requests = 50
        concurrency = 10

        def send_request(idx):
            s = time.time()
            try:
                resp = requests.post(
                    f"{GO_BASE}/v1/chat/completions",
                    json={
                        "model": "default",
                        "messages": [{"role": "user", "content": f"throughput {idx}"}],
                        "stream": False,
                    },
                    timeout=30,
                )
                elapsed = time.time() - s
                results.append((resp.status_code, elapsed))
            except Exception as e:
                results.append((-1, time.time() - s))

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(send_request, i) for i in range(num_requests)]
            concurrent.futures.wait(futures, timeout=120)

        total_time = time.time() - start_time
        success = sum(1 for code, _ in results if code == 200)
        failed = sum(1 for code, _ in results if code != 200 and code != 429)
        rate_limited = sum(1 for code, _ in results if code == 429)

        qps = success / total_time if total_time > 0 else 0
        success_latencies = [e for code, e in results if code == 200]
        avg_latency = statistics.mean(success_latencies) if success_latencies else 0

        print(f"\n  Throughput: success={success}/{num_requests}, rate_limited={rate_limited}, failed={failed}")
        print(f"  QPS={qps:.2f}, avg_latency={avg_latency:.3f}s, total_time={total_time:.1f}s")

        assert success > 0, "No successful requests"
        assert failed == 0, f"{failed} requests failed unexpectedly"


class TestStability:
    def test_short_stability_run(self):
        results = []
        duration = 60
        end_time = time.time() + duration

        def send_request():
            while time.time() < end_time:
                try:
                    resp = requests.post(
                        f"{GO_BASE}/v1/chat/completions",
                        json={
                            "model": "default",
                            "messages": [{"role": "user", "content": "stability test"}],
                            "stream": False,
                        },
                        timeout=30,
                    )
                    results.append((resp.status_code, time.time()))
                except:
                    results.append((-1, time.time()))
                time.sleep(0.5)

        threads = [threading.Thread(target=send_request) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=duration + 30)

        success_rate = sum(1 for code, _ in results if code == 200) / len(results) * 100
        error_count = sum(1 for code, _ in results if code in [500, 503])

        print(f"\n  Stability: total={len(results)}, success_rate={success_rate:.1f}%, errors={error_count}")
        assert success_rate >= 90, f"Success rate too low: {success_rate:.1f}%"

        metrics_resp = requests.get(f"{GO_BASE}/manage/metrics", timeout=5)
        if metrics_resp.status_code == 200:
            metrics = metrics_resp.json()
            goroutines = metrics.get("active_goroutines", 0)
            print(f"  Goroutines: {goroutines}")
            assert goroutines < 500, f"Too many goroutines: {goroutines}"


class TestLongConnection:
    def test_stream_stability(self):
        streams = []
        for i in range(5):
            resp = requests.post(
                f"{GO_BASE}/v1/chat/completions",
                json={
                    "model": "default",
                    "messages": [{"role": "user", "content": f"请写一首关于春天的诗，编号{i}"}],
                    "stream": True,
                },
                headers={"Accept": "text/event-stream"},
                stream=True,
                timeout=120,
            )
            streams.append((i, resp))

        results = []
        for idx, resp in streams:
            if resp.status_code != 200:
                results.append((idx, resp.status_code, 0, False))
                continue

            chunks = 0
            has_done = False
            for line in resp.iter_lines(decode_unicode=True):
                if line and "data:" in line:
                    chunks += 1
                    if "data: [DONE]" in line:
                        has_done = True

            results.append((idx, 200, chunks, has_done))

        for idx, code, chunks, has_done in results:
            if code == 200:
                assert chunks > 0, f"Stream {idx}: no chunks"
                assert has_done, f"Stream {idx}: missing [DONE]"

        successful = sum(1 for _, code, _, _ in results if code == 200)
        print(f"\n  Long connection: {successful}/{len(results)} streams completed successfully")
