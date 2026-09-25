# -*- coding: utf-8 -*-
"""导出 role 分类结果，便于人工抽查：data/_role_service.txt 与 data/_role_info.txt。

用法：python tools/dump_roles.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "portal.json"


def main() -> None:
    items = json.loads(DATA.read_text(encoding="utf-8"))["items"]
    buckets = {"service": [], "info": []}
    for item in items:
        line = f"{item['name']}  [{item['kind']}/{item['platform']}]  {item.get('url') or '(无网址：小程序/公众号)'}"
        buckets[item["role"]].append(line)
    for role, lines in buckets.items():
        out = ROOT / "data" / f"_role_{role}.txt"
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"{role}: {len(lines)} 条 -> {out.name}")


if __name__ == "__main__":
    main()
