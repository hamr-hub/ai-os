import os
import sys
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("MOCK_VLLM_PORT", 18888))
CHAT_FAIL = os.environ.get("MOCK_CHAT_FAIL", "0") == "1"
HEALTH_DELAY = float(os.environ.get("MOCK_HEALTH_DELAY", "1"))


class MockVLLMHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            time.sleep(HEALTH_DELAY)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/v1/chat/completions":
            if CHAT_FAIL:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "mock chat failure"}).encode())
                return

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length else "{}"
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            model = data.get("model", "mock-model")
            resp = {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Mock response from " + model},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 8, "total_tokens": 13},
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        sys.stderr.write(f"[mock-vllm] {format % args}\n")


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), MockVLLMHandler)
    print(f"Mock vLLM server starting on port {PORT}, chat_fail={CHAT_FAIL}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
