# -*- coding: utf-8 -*-
"""把 342 条按维度分组的紧凑清单导出来，便于人工核对分类是否合理。

用法：python tools/dump_facets.py  → data/_facets.txt
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "portal.json"
OUT = ROOT / "data" / "_facets.txt"

FIELDS = [("campus", "校区"), ("audience", "对象"), ("purpose", "用途"), ("kind", "形态")]


def main() -> None:
    items = json.loads(DATA.read_text(encoding="utf-8"))["items"]
    lines: list[str] = []
    for field, label in FIELDS:
        groups: dict[str, list[dict]] = defaultdict(list)
        for it in items:
            value = it.get(field)
            for v in (value if isinstance(value, list) else [value]):
                groups[v or "（空）"].append(it)
        lines.append(f"\n{'=' * 78}\n## 按{label}（{field}）\n")
        for value in sorted(groups, key=lambda v: -len(groups[v])):
            rows = groups[value]
            lines.append(f"\n### {value}（{len(rows)} 条）")
            for it in rows:
                desc = (it.get("desc") or "").replace("\n", " ")[:34]
                lines.append(f"  {it['name'][:26]:<28} {desc}")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"→ {OUT}（{len(items)} 条）")


if __name__ == "__main__":
    main()
