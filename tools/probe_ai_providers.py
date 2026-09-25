# -*- coding: utf-8 -*-
"""探测各家大模型接口在本机网络下是否可达（不带密钥，看返回码即可判断）。

- 401 / 403：接口可达，只是缺密钥 → 可以接入
- 404 / 400：接口可达（路径或参数问题）
- 连接失败 / DNS 失败 / 超时：本机网络到不了 → 不要推荐给用户

用法：python tools/probe_ai_providers.py → data/_ai_probe.txt
"""
from __future__ import annotations

import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "_ai_probe.txt"

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

PROVIDERS = [
    ("DeepSeek", "https://api.deepseek.com/v1/chat/completions", "deepseek-chat", "需要密钥（充值）"),
    ("智谱 GLM", "https://open.bigmodel.cn/api/paas/v4/chat/completions", "glm-4-flash", "glm-4-flash 免费档"),
    ("阿里云百炼·通义", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", "qwen-turbo", "新用户免费额度"),
    ("硅基流动", "https://api.siliconflow.cn/v1/chat/completions", "Qwen/Qwen2.5-7B-Instruct", "部分模型免费"),
    ("月之暗面 Kimi", "https://api.moonshot.cn/v1/chat/completions", "moonshot-v1-8k", "需充值"),
    ("火山方舟·豆包", "https://ark.cn-beijing.volces.com/api/v3/chat/completions", "doubao-1.5-lite", "新用户免费额度"),
    ("Pollinations（现默认）", "https://text.pollinations.ai/openai", "openai", "免费档已限额"),
    ("本地 Ollama", "http://127.0.0.1:11434/v1/chat/completions", "qwen2.5:3b", "完全离线、零成本"),
]


def dns(host: str) -> bool:
    try:
        socket.getaddrinfo(host, None)
        return True
    except OSError:
        return False


def probe(url: str, model: str) -> tuple[str, str, str]:
    host = urlparse(url).hostname or ""
    if not dns(host):
        return "DNS 解析失败", "", "本机网络到不了"
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer probe-no-key"},
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=12, context=CTX) as resp:
            return f"HTTP {resp.status}", f"{time.time() - started:.1f}s", "可达"
    except urllib.error.HTTPError as exc:
        body = exc.read(160).decode("utf-8", "ignore").replace("\n", " ")
        verdict = "可达（缺密钥/参数）" if exc.code in (400, 401, 403, 404, 422, 429) else "异常"
        return f"HTTP {exc.code}", f"{time.time() - started:.1f}s", f"{verdict}｜{body[:90]}"
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__, f"{time.time() - started:.1f}s", "本机网络到不了"


def main() -> None:
    lines = ["各家大模型接口可达性实测（不带有效密钥）", ""]
    for name, url, model, note in PROVIDERS:
        status, elapsed, verdict = probe(url, model)
        lines.append(f"{name:<22} {status:<18} {elapsed:<7} {verdict}")
        lines.append(f"{'':22} {url}   （{note}）")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
