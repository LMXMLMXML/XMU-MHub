# -*- coding: utf-8 -*-
"""列出"文章型 URL"与"名称就是说明/公告"的条目，供人工确认哪些是纯讲解页。

判据（两类，均不看描述文本，避免误伤机构门户）：
A. 文章型 URL：/info/<栏目>/<文章>.htm、/<年>/<日期>/、news.*、.pdf、/xwdt/、/tzgg/ 等；
B. 名称以 指南/须知/说明/公告/通知/指引/手册/教程/流程/简介/概况/问答/攻略 结尾或包含之。

用法：python tools/inventory_guides.py → data/_guide_inventory.txt
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "portal.json"
OUT = ROOT / "data" / "_guide_inventory.txt"

ARTICLE_URL = re.compile(
    r"/info/\d+/\d+\.htm|/\d{4}/\d{4}/|news\.xmu\.edu\.cn|\.pdf($|\?)|/xwdt/|/tzgg/|/ggtz/",
    re.I,
)
NAME_WORDS = ("指南", "须知", "说明", "公告", "通知", "指引", "手册", "教程",
              "办理流程", "操作流程", "简介", "概况", "问答", "攻略", "常见问题")


def main() -> None:
    items = json.loads(DATA.read_text(encoding="utf-8"))["items"]
    art, named = [], []
    for item in items:
        name, url = item["name"], item.get("url") or ""
        if url and ARTICLE_URL.search(url):
            art.append((name, item.get("kind"), item.get("platform"), url))
        elif any(w in name for w in NAME_WORDS):
            named.append((name, item.get("kind"), item.get("platform"), url))

    lines = [f"条目总数 {len(items)}", "", f"== A. 文章型 URL（{len(art)} 条）=="]
    for name, kind, platform, url in art:
        lines.append(f"  · {name}  [{kind}/{platform}]  {url}")
    lines.append("")
    lines.append(f"== B. 名称像说明页（且不是文章型 URL）（{len(named)} 条）==")
    for name, kind, platform, url in named:
        lines.append(f"  · {name}  [{kind}/{platform}]  {url or '（无网址）'}")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"A 文章型 {len(art)} 条｜B 名称像说明页 {len(named)} 条｜见 {OUT}")


if __name__ == "__main__":
    main()
