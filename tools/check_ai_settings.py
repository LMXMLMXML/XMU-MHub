# -*- coding: utf-8 -*-
"""验证"自己填 Key"这套流程：状态 → 保存 Key → 优先引擎 → 清除 Key → 问答降级。

用法：先启动后端，再 python tools/check_ai_settings.py
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
        with urllib.request.urlopen(url, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    st = call("/api/ai")
    print(f"1) 初始状态：引擎={st['label']}｜链={st['chain']}")
    for p in st["providers"]:
        print(f"   - {p['label']:<10} 需Key={p['needsKey']} 已配置={p['hasKey']} 就绪={p['ready']} ({p['model']})")

    save = call("/api/ai/key", {"provider": "zhipu", "key": "test-key-1234567890"})
    print(f"\n2) 填入假 Key 后：{save['status']['label']}｜链={save['status']['chain']}")
    print(f"   回传的 Key 提示：{next(p['keyHint'] for p in save['status']['providers'] if p['id'] == 'zhipu')}")
    print(f"   是否回传明文 Key：{'是' if 'test-key' in json.dumps(save) else '否（正确）'}")

    pref = call("/api/ai/preferred", {"provider": "dashscope"})
    print(f"\n3) 设通义为优先：链={pref['status']['chain']}｜preferred={pref['status']['preferred']}")

    ask = call("/api/ask", {"question": "宿舍水管漏了找谁"})
    print(f"\n4) 提问（Key 是假的，应逐级降级）：engine={ask.get('engine')}")
    print(f"   原因：{(ask.get('note') or '')[:110]}")
    print(f"   回答：{(ask.get('answer') or '')[:90]}")

    clear = call("/api/ai/key", {"provider": "zhipu", "key": ""})
    clear = call("/api/ai/key", {"provider": "dashscope", "key": ""})
    call("/api/ai/preferred", {"provider": ""})
    print(f"\n5) 清除全部 Key 后：引擎={clear['status']['label']}｜链={clear['status']['chain']}")

    local = call("/api/ask", {"question": "怎么报销"})
    print(f"6) 无 Key 提问：engine={local.get('engine')}")
    print(f"   回答：{(local.get('answer') or '')[:110]}")


if __name__ == "__main__":
    main()
