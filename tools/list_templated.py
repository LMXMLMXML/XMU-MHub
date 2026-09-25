# -*- coding: utf-8 -*-
"""列出"靠模板凑出来"的说明（这些就是用户说的牛头不对马嘴），供改写。

用法：python tools/list_templated.py → data/_templated.txt
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "portal.json"
OUT = Path(__file__).resolve().parent.parent / "data" / "_templated.txt"

GENERIC = [
    "部门职责、办事流程、表格下载与通知公告",
    "厦门大学在线服务入口",
    "学院概况、师资队伍、本研培养方案",
    "研究团队、研究方向、科研平台与学术成果",
    "实验室简介、研究方向、大型仪器与开放共享",
    "组织概况、活动通知与面向师生的服务",
    "刊物/出版信息与投稿、订阅渠道",
    "校区概况、办事指南、通知公告与生活服务信息",
]


def main() -> None:
    items = json.loads(DATA.read_text(encoding="utf-8"))["items"]
    hits = []
    for it in items:
        desc = it.get("desc") or ""
        for g in GENERIC:
            if g in desc:
                hits.append((g, it["name"], desc, it.get("url") or ""))
                break
    lines = [f"模板化说明 {len(hits)} / {len(items)} 条", ""]
    for g, name, desc, url in sorted(hits):
        lines.append(f"[{g[:12]}] {name}")
        lines.append(f"    {desc}")
        lines.append(f"    {url or '（无网址）'}")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"模板化说明 {len(hits)} 条 → {OUT.name}")


if __name__ == "__main__":
    main()
