"""实测「AI 找入口」：真实调用免费 AI（Pollinations），记录引擎、耗时与回答。"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

PORT_FILE = Path(r"D:\AI\xmu_hub\data\_runtime_port.txt")


def runtime_port() -> int:
    try:
        return int(PORT_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return 8765


BASE = "http://127.0.0.1:" + str(runtime_port())
OUT = Path(r"D:\AI\xmu_hub\data\_ai_live.txt")


def call(path: str, payload: dict | None = None, timeout: int = 120):
    if payload is None:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


lines = [f"引擎状态：{call('/api/ai')}"]

questions = [
    "宿舍水管漏了找谁",
    "我是研究生，手机上怎么查成绩",
    "校友想进校看看要预约吗",
    "在电脑上怎么报销",
]

for q in questions:
    start = time.time()
    res = call("/api/ask", {"question": q})
    cost = time.time() - start
    lines.append(f"\n问：{q}")
    lines.append(f"  引擎={res.get('engine')} 标签={res.get('label')} 模型={res.get('model')} "
                 f"耗时={cost:.1f}s 缓存={res.get('cached', False)}")
    lines.append(f"  回答：{res.get('answer')}")
    lines.append(f"  推荐条目：{res.get('items')}")
    if res.get("note"):
        lines.append(f"  备注：{res.get('note')}")

# 缓存命中验证
start = time.time()
again = call("/api/ask", {"question": questions[0]})
lines.append(f"\n重复提问（应命中缓存）：耗时={time.time() - start:.2f}s 缓存={again.get('cached', False)}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("written")
