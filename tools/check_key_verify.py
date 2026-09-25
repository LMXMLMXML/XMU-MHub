# -*- coding: utf-8 -*-
"""验证"填 Key 即时验证"：好 Key 通过、错 Key 当场报出人话原因、模型名写错也能提示。

用法：先启动后端，再 python tools/check_key_verify.py
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

PORT_FILE = Path(__file__).resolve().parent.parent / "data" / "_runtime_port.txt"


def call(path: str, payload: dict | None = None) -> dict:
    port = PORT_FILE.read_text(encoding="utf-8").strip()
    url = f"http://127.0.0.1:{port}{path}"
    if payload is None:
        with urllib.request.urlopen(url, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


CASES = [
    ("智谱 GLM 假 Key", "zhipu", "sk-this-key-is-not-real-123456", ""),
    ("DeepSeek 假 Key", "deepseek", "sk-fake-key-1234567890abcdef", ""),
    ("豆包 不填接入点 ID", "ark", "fake-ark-key-123456", ""),
    ("通义 假 Key", "dashscope", "sk-fake-1234567890", ""),
]


def main() -> None:
    for label, provider, key, model in CASES:
        res = call("/api/ai/key", {"provider": provider, "key": key, "model": model})
        v = res.get("verify") or {}
        print(f"· {label}")
        print(f"    验证：{'通过' if v.get('ok') else '失败'}｜{v.get('message')}")
        if v.get("detail"):
            print(f"    平台原文：{v['detail'][:80]}")
        call("/api/ai/key", {"provider": provider, "key": ""})       # 清掉，别留假 Key

    print("\n· 清除后状态")
    st = call("/api/ai")
    print(f"    引擎={st['label']}｜链={st['chain']}")
    ud = json.loads((PORT_FILE.parent / "userdata.json").read_text(encoding="utf-8"))
    print(f"    userdata 里的 Key：{ud.get('aiKeys')}")


if __name__ == "__main__":
    main()
