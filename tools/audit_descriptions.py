# -*- coding: utf-8 -*-
"""质量审计 C：说明文案本身的问题——重复模板、可疑字串、与条目类型不符。

用法：python tools/audit_descriptions.py → 屏幕输出 + data/_desc_audit.txt
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "portal.json"
OUT = ROOT / "data" / "_desc_audit.txt"

SUSPECT = ("厦门大学二", "某某", "TODO", "待补", "示例")

# 这些单位不该用"部门职责/办事流程/表格下载"这种话术
NOT_PROCESS = ("编辑部", "研究院", "实验室", "中心", "博物馆", "档案馆", "图书馆",
               "出版社", "资产经营", "学报", "同学会", "老年大学", "关工委", "科协",
               "工会", "团委", "妇联", "妇女委员会", "宣传部", "统战部")


def main() -> int:
    items = json.loads(DATA.read_text(encoding="utf-8"))["items"]
    lines: list[str] = []

    dup = collections.Counter((it.get("desc") or "") for it in items)
    lines.append("== 重复说明（同一条说明被用在多个条目上）==")
    for desc, n in dup.most_common():
        if n > 1 and desc:
            names = [it["name"] for it in items if (it.get("desc") or "") == desc]
            lines.append(f"  {n:>3} 条：{desc[:56]}")
            lines.append(f"        用于：{'、'.join(names[:8])}{' …' if len(names) > 8 else ''}")

    lines.append("\n== 含可疑字串的说明 ==")
    for it in items:
        desc = it.get("desc") or ""
        for word in SUSPECT:
            if word in desc:
                lines.append(f"  {it['name']}：{desc[:70]}")

    lines.append("\n== 话术与单位类型不符 ==")
    for it in items:
        name, desc = it["name"], it.get("desc") or ""
        if "部门职责、办事流程、表格下载" in desc and name.endswith(NOT_PROCESS):
            lines.append(f"  {name}：{desc[:70]}")

    lines.append("\n== 短说明（<14 字）==")
    for it in items:
        desc = it.get("desc") or ""
        if len(desc) < 14:
            lines.append(f"  {len(desc):>3} 字  {it['name']}：{desc}")

    # 机构门户的标签现状
    org = [it for it in items if (it.get("source") or "").startswith("组织机构") or "组织机构" in (it.get("source") or "")]
    lines.append(f"\n== 来自「组织机构」章节的条目（{len(org)} 条）的标签 ==")
    for it in org[:60]:
        lines.append(f"  {it['name'][:22]:<24} 对象={'/'.join(it.get('audience') or [])} "
                     f"用途={'/'.join(it.get('purpose') or [])}")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:80]))
    print(f"\n…完整结果见 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
