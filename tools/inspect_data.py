"""目录数据体检：端分布、简介覆盖率与抽样。"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

# --- 仓库根目录，随 clone 位置自适应（原来这里写死了 D:\AI\xmu_hub）---
ROOT = Path(__file__).resolve().parent.parent


DATA = ROOT / "data" / "portal.json"
OUT = ROOT / "data" / "_inspect.txt"

items = json.loads(DATA.read_text(encoding="utf-8"))["items"]
lines: list[str] = []

lines.append(f"条目总数：{len(items)}")
lines.append("端分布：" + str(dict(Counter(i["platform"] for i in items))))
lines.append("形态分布：" + str(dict(Counter(i["kind"] for i in items))))
lines.append("简介长度：最短 %d / 中位 %d / 最长 %d" % (
    min(len(i["desc"]) for i in items),
    sorted(len(i["desc"]) for i in items)[len(items) // 2],
    max(len(i["desc"]) for i in items),
))

lines.append("\n=== 端分布抽样 ===")
for platform in ("pc", "mobile", "both", "offline"):
    sample = [i for i in items if i["platform"] == platform][:4]
    lines.append(f"[{platform}] 共 {sum(1 for i in items if i['platform'] == platform)} 条")
    for it in sample:
        lines.append(f"   {it['name']}｜{it['desc'][:64]}")

lines.append("\n=== 简介最短的 25 条（人工检查口吻是否自然）===")
for it in sorted(items, key=lambda x: len(x["desc"]))[:25]:
    lines.append(f"  ({len(it['desc'])}) {it['name']}｜{it['desc']}")

lines.append("\n=== 端分类抽查（易混淆条目）===")
for name in ('"掌上校史馆"', "24365 就业育人数智平台、校友捐赠", "图书馆座位预约",
             "体育场馆（篮球场等）预约", "校园一卡通充值", "迎新系统", "漳州校区场馆",
             "厦大数字校园卡", "厦门大学访客预约系统", "XMULibrary"):
    for it in items:
        if it["name"] == name:
            lines.append(f"  {name}｜kind={it['kind']}｜platform={it['platform']}（{it['platformLabel']}）")
            break
    else:
        lines.append(f"  {name}｜（未收录）")

lines.append("\n=== 端分布明细（带形态，便于发现误判）===")
for platform in ("mobile", "both", "offline"):
    lines.append(f"[{platform}] 共 {sum(1 for i in items if i['platform'] == platform)} 条")
    for it in [i for i in items if i["platform"] == platform]:
        lines.append(f"   {it['name']}｜{it['kind']}｜{it['platformLabel']}")

lines.append("\n=== 重点条目简介 ===")
for name in ("厦门大学主页", "新闻网", "教务服务平台", "图书馆", "附属第一医院",
             "信息学院（特色化示范性软件学院）", "档案馆、文博管理中心", "财务处",
             "翔安校区管委会", "厦门大学医院", "招生网", "易班厦大"):
    for it in items:
        if it["name"] == name:
            lines.append(f"  {name} [{it['platformLabel']}／{it['kindLabel']}]：{it['desc']}")
            break
    else:
        lines.append(f"  {name}：（未收录）")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("written", len(items))
