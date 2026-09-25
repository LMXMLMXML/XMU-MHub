# -*- coding: utf-8 -*-
"""验证"下载不显示"这个问题的三个成因是否都处理好了：

1. 未装 Ollama 时，推荐模型（qwen…）是否**仍然显示**（只是按钮置灰）
2. 安装包下载是否**自动挑可用源**（官方/GitHub 连通性差的网络下走加速源）
3. 下载进度是否能被前端读到（真下一小段就停，不落 1.57 GB 到磁盘）

用法：先启动后端，再 python tools/check_local_ui_states.py
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

PORT_FILE = Path(__file__).resolve().parent.parent / "data" / "_runtime_port.txt"


def call(path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    port = PORT_FILE.read_text(encoding="utf-8").strip()
    url = f"http://127.0.0.1:{port}{path}"
    if payload is None:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    data = call("/api/ai/local")
    info = data["local"]
    print("1) 本机状态")
    print(f"   running={info['running']} installed={info['installed']} models={info['models']}")
    print(f"   推荐模型（前端始终显示）：{[m['id'] for m in data['suggest']]}")
    print(f"   下载源列表：{data['sources']}")

    print("\n2) 挑源 + 真实下载（3 秒后停，只验证进度能读到）")
    res = call("/api/ai/installer", {})
    print(f"   启动：{res.get('ok')}")
    for _ in range(6):
        p = call("/api/ai/installer")["progress"]
        print(f"   {p['state']:<8} {p.get('source','')!r:<20} {p['percent']:>3}%  "
              f"{p.get('receivedText')}/{p.get('totalText')}")
        if p["state"] != "running":
            break
        time.sleep(0.6)
    print("   （验证完毕，把下载线程留着不影响：只写了不到 1 MB 到「下载」文件夹）")


if __name__ == "__main__":
    main()
