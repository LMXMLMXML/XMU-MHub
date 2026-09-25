# -*- coding: utf-8 -*-
"""验证"一键下载 + 进度条"：用假 Ollama 模拟拉取流，检查进度是否被正确统计。

假 Ollama 的 /api/pull 会分块吐 NDJSON（带 total/completed），本脚本轮询本软件的
/api/ai/pull，把进度打印出来，最后确认模型被自动切换。

用法：python tools/check_pull_progress.py
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT_FILE = Path(__file__).resolve().parent.parent / "data" / "_runtime_port.txt"
LAYERS = [("sha256:aaa", 4_000_000), ("sha256:bbb", 6_000_000)]


class FakePull(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):  # noqa: N802
        body = json.dumps({"models": []}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        def emit(obj):
            self.wfile.write((json.dumps(obj) + "\n").encode())
            self.wfile.flush()
        emit({"status": "pulling manifest"})
        # 真实 Ollama 会先把所有层的 total 报出来，再逐层下载——测试也要这样才真实
        for digest, total in LAYERS:
            emit({"status": "pulling", "digest": digest, "total": total, "completed": 0})
        for digest, total in LAYERS:
            step = total // 4
            for i in range(1, 5):
                emit({"status": "downloading", "digest": digest,
                      "total": total, "completed": step * i})
                time.sleep(0.25)
            emit({"status": "verifying sha256 digest", "digest": digest})
        emit({"status": "writing manifest"})
        emit({"status": "success"})


def app_call(path: str, payload: dict | None = None) -> dict:
    port = PORT_FILE.read_text(encoding="utf-8").strip()
    url = f"http://127.0.0.1:{port}{path}"
    if payload is None:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 11434), FakePull)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("假 Ollama（/api/pull 流式）已启动")

    res = app_call("/api/ai/pull", {"model": "qwen2.5:3b"})
    print(f"启动下载：ok={res.get('ok')}")
    seen: list[str] = []
    for _ in range(40):
        p = app_call("/api/ai/pull")["progress"]
        line = f"{p['state']:<8} {p['percent']:>3}%  {p['completedText']}/{p['totalText']}  {p['status']}"
        if not seen or seen[-1] != line:
            seen.append(line)
            print("  " + line)
        if p["state"] in ("done", "error"):
            break
        time.sleep(0.3)
    print(f"进度采样 {len(seen)} 个不同状态")


if __name__ == "__main__":
    main()
