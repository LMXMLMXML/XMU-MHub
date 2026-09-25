# -*- coding: utf-8 -*-
"""验证"形状不对的 Key 会被当场拦下"（太短 / 含空格 / 智谱缺后半段 / 像样的假 sk-）。

用法：先启动一个测试实例（python app.py --port 8788 --no-window），再运行本脚本。
"""
from __future__ import annotations

import json
import urllib.request

PORT = 8788

CASES = [
    ("你贴的那串（5 位）", "deepseek", "LMXML"),
    ("含空格的 Key", "deepseek", "sk-abc def1234567890"),
    ("智谱缺后半段（无点）", "zhipu", "abcdefghijklmnop"),
    # 注意：这里的假 Key 刻意不用 "sk-" + 32 位十六进制。那种写法虽然也是假的，
    # 但会撞上 GitHub 的 push protection 密钥扫描（它只看格式不看上下文），
    # 导致整个仓库推不上去。长度足够通过形状检查、值一眼可辨是占位符即可。
    ("像样的假 sk-（格式对、值错）", "deepseek", "sk-EXAMPLE-not-a-real-key-placeholder"),
]


def post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    for label, provider, key in CASES:
        res = post("/api/ai/key", {"provider": provider, "key": key, "model": ""})
        verify = res.get("verify") or {}
        verdict = "通过" if verify.get("ok") else "拦下"
        print(f"· {label}")
        print(f"    保存={res.get('ok')}｜{verdict}｜{verify.get('message')}")
        if verify.get("detail"):
            print(f"    平台原文：{verify['detail'][:90]}")
    status = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/ai", timeout=10).read())
    print(f"\n最终：引擎={status['label']}｜已配 Key 数={sum(1 for p in status['providers'] if p['hasKey'])}（应为 0）")


if __name__ == "__main__":
    main()
