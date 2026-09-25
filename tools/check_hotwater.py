# -*- coding: utf-8 -*-
"""热水/水控回归检查：确认各校区热水相关说法与入口都能被搜到、且 AI 候选中排得上。

用法：python tools/check_hotwater.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as hub  # noqa: E402

QUERIES = [
    "翔安热水怎么用",
    "翔安宿舍洗澡怎么扣费",
    "宿舍热水小程序",
    "热水消费系统",
    "嘉庚学院热水预约",
    "蓝牙水控怎么连",
    "热水器坏了找谁",
]

def main() -> int:
    catalog = hub.Catalog()
    print(f"目录共 {len(catalog.items)} 条\n")
    bad = 0
    for q in QUERIES:
        hits = hub.search(catalog, q)
        print(f"「{q}」命中 {len(hits)} 条")
        for item in hits[:4]:
            print(f"  · {item['name']}（{item.get('campus', '')} / {item.get('platform', '')}）")
        inferred = hub.infer_filters(q)
        cands = hub.ai_candidates(catalog, q, inferred)
        names = [c["name"] for c in cands]
        print(f"  AI 候选前 5：{' | '.join(names[:5]) or '（无）'}")
        if not hits:
            bad += 1
        print()
    print(f"无结果查询数：{bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
