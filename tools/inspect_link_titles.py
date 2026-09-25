# -*- coding: utf-8 -*-
"""看看"标题可疑"到底有多可信：按相似度分桶列出样例，用于校准阈值。

用法：python tools/inspect_link_titles.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "link_status.json"


def main() -> None:
    data = {k: v for k, v in json.loads(DATA.read_text(encoding="utf-8")).items()
            if isinstance(v, dict)}
    buckets: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
    for name, info in data.items():
        sim = info.get("similar", -1)
        title = info.get("title") or ""
        if not title:
            buckets["无标题"].append((name, sim, title))
            continue
        if sim < 0.2:
            key = "0.0–0.2 极低"
        elif sim < 0.35:
            key = "0.2–0.35 低"
        elif sim < 0.5:
            key = "0.35–0.5 偏低"
        elif sim < 0.75:
            key = "0.5–0.75 中等"
        else:
            key = "0.75+ 高（正常）"
        buckets[key].append((name, sim, title))
    for key in ["无标题", "0.0–0.2 极低", "0.2–0.35 低", "0.35–0.5 偏低", "0.5–0.75 中等", "0.75+ 高（正常）"]:
        rows = buckets.get(key, [])
        print(f"\n== {key}（{len(rows)} 条）==")
        for name, sim, title in sorted(rows, key=lambda r: r[1])[:8]:
            print(f"  [{sim:+.2f}] {name[:26]:<28} 实际标题：{title[:40]}")


if __name__ == "__main__":
    main()
