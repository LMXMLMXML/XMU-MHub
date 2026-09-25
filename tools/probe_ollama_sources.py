# -*- coding: utf-8 -*-
"""探测 Ollama 安装包在本机网络下能不能下（官方源 + 常见 GitHub 加速源）。

用法：python tools/probe_ollama_sources.py
"""
from __future__ import annotations

import time
import urllib.request

UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")}

GH = "https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe"
SOURCES = [
    ("官方 ollama.com", "https://ollama.com/download/OllamaSetup.exe"),
    ("GitHub 直连", GH),
    ("ghproxy.net", "https://ghproxy.net/" + GH),
    ("gh-proxy.com", "https://gh-proxy.com/" + GH),
    ("ghfast.top", "https://ghfast.top/" + GH),
    ("moeyy 加速", "https://github.moeyy.xyz/" + GH),
]


def main() -> None:
    ok = []
    for name, url in SOURCES:
        started = time.time()
        try:
            req = urllib.request.Request(url, method="HEAD", headers=UA)
            with urllib.request.urlopen(req, timeout=15) as resp:
                size = resp.headers.get("Content-Length")
                print(f"{name:<16} HTTP {resp.status} | {size} B | {time.time() - started:.1f}s")
                if resp.status == 200:
                    ok.append((name, url))
        except Exception as exc:  # noqa: BLE001
            print(f"{name:<16} {type(exc).__name__} | {time.time() - started:.1f}s")
    print("\n可用源：" + ("；".join(n for n, _ in ok) if ok else "（本网络下都不可用）"))


if __name__ == "__main__":
    main()
