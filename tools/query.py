"""按关键词查询目录条目：python tools/query.py 热水 水控

输出含名称、端/形态、校区标签与来源，便于快速核对数据。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8")

# --- 仓库根目录，随 clone 位置自适应（原来这里写死了 D:\AI\xmu_hub）---
ROOT = Path(__file__).resolve().parent.parent


DATA = ROOT / "data" / "portal.json"


def main() -> None:
    keywords = sys.argv[1:]
    items = json.loads(DATA.read_text(encoding="utf-8"))["items"]
    print(f"目录共 {len(items)} 条")
    if not keywords:
        return
    for kw in keywords:
        hits = [
            i for i in items
            if kw in i["name"]
            or kw in (i.get("desc") or "")
            or kw in " ".join(i.get("keywords", []))
        ]
        print(f"\n「{kw}」命中 {len(hits)} 条")
        for i in hits:
            campus = "/".join(i.get("campus", []))
            print(f"  · {i['name']}")
            print(f"      端={i['platformLabel']} 形态={i['kindLabel']} 校区={campus}")
            print(f"      {i['desc'][:80]}")
            if i.get("url"):
                print(f"      {i['url']}")


if __name__ == "__main__":
    main()
