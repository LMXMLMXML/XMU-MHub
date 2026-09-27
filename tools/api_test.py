"""门户接口自测：以 UTF-8 正常发送中文，验证检索与 AI 降级。"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

# --- 仓库根目录，随 clone 位置自适应（原来这里写死了 D:\AI\xmu_hub）---
ROOT = Path(__file__).resolve().parent.parent


PORT_FILE = ROOT / "data" / "_runtime_port.txt"


def runtime_port() -> int:
    """读取程序实际监听端口，避免端口被旧实例占用时测试打到旧数据。"""
    try:
        return int(PORT_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return 8765


BASE = "http://127.0.0.1:" + str(runtime_port())
OUT = ROOT / "data" / "_api_test.txt"


def call(path: str, payload: dict | None = None):
    if payload is None:
        with urllib.request.urlopen(BASE + path, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


lines: list[str] = []
cat = call("/api/catalog")
lines.append(f"catalog: items={len(cat['items'])} facets={cat['facets']['total']}")

for query in ["成绩", "宿舍水管漏了", "报销", "预约进校", "游泳", "饭卡充值", "论文查重"]:
    res = call("/api/search", {"query": query, "limit": 5})
    names = [f"{i['name']}({i['kindLabel']})" for i in res["items"]]
    lines.append(f"\n[search] {query}\n  -> " + " | ".join(names) or "  -> (空)")

for payload in [
    {"campus": "翔安校区", "purpose": "生活", "limit": 8},
    {"campus": "漳州校区", "limit": 8},
    {"audience": "研究生", "purpose": "学习", "limit": 8},
    {"audience": "校友", "limit": 8},
    {"kind": "miniprogram", "limit": 12},
    {"platform": "mobile", "limit": 10},
    {"platform": "pc", "limit": 6},
    {"platform": "both", "limit": 6},
    {"platform": "mobile", "purpose": "生活", "limit": 8},
]:
    res = call("/api/search", payload)
    names = [i["name"] for i in res["items"]]
    lines.append(f"\n[filter] {payload}\n  -> " + " | ".join(names))

lines.append(f"\n[ai 状态] {call('/api/ai')}")

lines.append("\n[简介覆盖率]")
cat_items = cat["items"]
short = [i["name"] for i in cat_items if len(i.get("desc") or "") < 10]
lines.append(f"  共 {len(cat_items)} 条，简介不足 10 字的 {len(short)} 条：{short}")
no_platform = [i["name"] for i in cat_items if not i.get("platformLabel")]
lines.append(f"  缺少端标签的 {len(no_platform)} 条：{no_platform}")

for question in ["我是研究生，在哪里查成绩", "宿舍水管漏了找谁", "校友想进校看看要预约吗"]:
    res = call("/api/ask", {"question": question})
    lines.append(f"\n[ask] {question}\n  engine={res.get('engine')} items={res.get('items')}\n  {res.get('answer')}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("written", OUT)
