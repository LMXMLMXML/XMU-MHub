# -*- coding: utf-8 -*-
"""目录统计：给 README / 交付说明提供可复制的准确数字。

用法：python tools/stats.py
"""
from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "portal.json"


def main() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    items = payload["items"]
    print(f"条目总数        : {len(items)}")
    print(f"精选 featured   : {sum(1 for i in items if i.get('featured'))}")
    print(f"无链接          : {sum(1 for i in items if not i.get('url'))}")
    print(f"端 platform     : {dict(Counter(i.get('platform') for i in items))}")
    print(f"形态 kind       : {dict(Counter(i.get('kind') for i in items))}")
    print(f"角色 role       : {dict(Counter(i.get('role') for i in items))}")
    info = [i["name"] for i in items if i.get("role") == "info"]
    service = [i["name"] for i in items if i.get("role") == "service"]
    print(f"  可用入口示例  : {'、'.join(service[:12])}")
    print(f"  机构/说明示例 : {'、'.join(info[:12])}")
    campus = Counter()
    for i in items:
        value = i.get("campus") or []
        if isinstance(value, str):
            value = [value]
        for c in value or ["未标注"]:
            campus[c] += 1
    print(f"校区 campus     : {dict(campus)}")
    lengths = [len(i.get("desc") or "") for i in items]
    print(f"简介长度        : 最短 {min(lengths)} / 中位 {int(statistics.median(lengths))} / 最长 {max(lengths)}")
    print(f"简介 < 10 字    : {sum(1 for n in lengths if n < 10)}")
    missing = [i["name"] for i in items if not (i.get("desc") or "").strip()]
    print(f"缺简介          : {len(missing)}{'（' + '、'.join(missing[:5]) + '）' if missing else ''}")


if __name__ == "__main__":
    main()
