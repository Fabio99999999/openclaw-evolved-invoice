"""MLX inference server - handles DeepSeek chat template correctly."""
import json, sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

import mlx.core as mx
from mlx_lm import load, generate

MODEL = "lmstudio-community/DeepSeek-R1-0528-Qwen3-8B-MLX-4bit"
model, tokenizer = None, None

def load_model():
    global model, tokenizer
    if model is None:
        model, tokenizer = load(MODEL)
        mem = mx.metal.get_active_memory() / 1024 / 1024
        print(f"Loaded. GPU: {mem:.0f} MB", flush=True)

def apply_chat(messages):
    """Apply chat template safely."""
    if tokenizer and tokenizer.chat_template:
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        prompt = "\n".join(f"{m['role']}: {m.get('content','')}" for m in messages)
        prompt += "\nassistant: "
    return prompt

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        
        load_model()
        messages = body.get("messages", [])
        max_tokens = body.get("max_tokens", 2048)
        stream = body.get("stream", False)
        
        if stream:
            self.send_error(400, "Streaming not supported")
            return
        
        prompt = apply_chat(messages)
        response = generate(model, tokenizer, prompt, max_tokens=max_tokens, verbose=False)
        
        result = {
            "id": "mlx-local",
            "object": "chat.completion", "model": MODEL,
            "created": 0,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": response}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())
    
    def do_GET(self):
        if "/models" in self.path or "/v1/models" in self.path:
            result = {"object": "list", "data": [{"id": MODEL, "object": "model"}]}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        else:
            self.send_error(404)
    
    def log_message(self, *a): pass

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11435
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"Server on :{port}", flush=True)
    server.serve_forever()
