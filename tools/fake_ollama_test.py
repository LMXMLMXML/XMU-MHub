# -*- coding: utf-8 -*-
"""用一个假 Ollama 服务验证"本机模型"整条链路（不需要真的安装 Ollama）。

起一个监听 11434 的最小 HTTP 服务，提供：
  GET  /api/tags     → 模型列表
  GET  /v1/models    → 就绪探测用
  POST /v1/chat/completions → 返回一段固定回答
然后调用本软件的 /api/ai/local 看是否识别、能否切换、能否真的问答。

用法：python tools/fake_ollama_test.py
"""
from __future__ import annotations

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT_FILE = Path(__file__).resolve().parent.parent / "data" / "_runtime_port.txt"
MODELS = ["qwen2.5:3b", "qwen2.5:7b-instruct"]


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 静音
        pass

    def _json(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/tags"):
            self._json({"models": [{"name": m} for m in MODELS]})
        elif self.path.startswith("/v1/models"):
            self._json({"object": "list", "data": [{"id": m} for m in MODELS]})
        else:
            self._json({})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        self._json({"choices": [{"message": {"content": "推荐 厦大后勤（假 Ollama 回答）\nPICK: 1"}}]})


def app_call(path: str, payload: dict | None = None) -> dict:
    port = PORT_FILE.read_text(encoding="utf-8").strip()
    url = f"http://127.0.0.1:{port}{path}"
    if payload is None:
        with urllib.request.urlopen(url, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 11434), Fake)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("假 Ollama 已启动（127.0.0.1:11434）")

    print(f"1) 检测：{json.dumps(app_call('/api/ai/local')['local'], ensure_ascii=False)}")
    res = app_call("/api/ai/local", {"model": MODELS[0]})
    print(f"2) 切到 {MODELS[0]}：ok={res.get('ok')}｜验证={res.get('verify', {}).get('message')}")
    print(f"   引擎链={res['status']['chain']}")
    ask = app_call("/api/ask", {"question": "宿舍报修找谁"})
    print(f"3) 问答：engine={ask.get('engine')}｜answer={((ask.get('answer') or '')[:60])}")

    print("4) 换回默认（清除本机模型优先）")
    app_call("/api/ai/preferred", {"provider": ""})
    print(f"   链={app_call('/api/ai')['chain']}")
    server.shutdown()


if __name__ == "__main__":
    main()
