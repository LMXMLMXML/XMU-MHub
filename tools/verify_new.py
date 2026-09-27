"""核对新增条目与整体完整性。"""

from __future__ import annotations

import json
from pathlib import Path

# --- 仓库根目录，随 clone 位置自适应（原来这里写死了 D:\AI\xmu_hub）---
ROOT = Path(__file__).resolve().parent.parent


DATA = ROOT / "data" / "portal.json"
OUT = ROOT / "data" / "_verify_new.txt"

items = json.loads(DATA.read_text(encoding="utf-8"))["items"]
by_name = {i["name"]: i for i in items}
lines: list[str] = [f"总条目：{len(items)}"]

expected_new = [
    "学生宿舍水控（热水）使用指南", "心理咨询预约系统", "失物招领平台",
    "学习共享空间自习室预约", "体测预约与成绩查询", "马上办（学生事务）",
    "厦大易班（校站）", "讲座信息",
]
lines.append("\n=== 本次补充的条目 ===")
for name in expected_new:
    it = by_name.get(name)
    if it:
        lines.append(f"  ✅ {name}｜{it['platformLabel']}／{it['kindLabel']}｜{it['url'][:60]}")
        lines.append(f"      简介：{it['desc'][:70]}")
    else:
        lines.append(f"  ❌ {name}：未收录")

lines.append("\n=== 关键老条目是否还在（防止解析回归）===")
for name in ("厦门大学主页", "教务服务平台", "图书馆", "XMULibrary", "厦大数字校园卡",
             "参观厦大", "XMUSPORTS", "财务处", "校医院" if "校医院" in by_name else "厦门大学医院",
             "学生就业创业指导中心", "校友总会", "校园网服务指南", "厦大云盘"):
    it = by_name.get(name)
    lines.append(f"  {'✅' if it else '❌'} {name}")

lines.append("\n=== 检索新条目 ===")
for kw in ("热水", "洗澡", "淋浴", "心理", "失物", "自习", "体测", "易班"):
    hits = [i["name"] for i in items
            if kw in i["name"] or kw in (i.get("desc") or "")
            or kw in " ".join(i.get("keywords", [])) or kw in (i.get("entry") or "")]
    lines.append(f"  「{kw}」→ {len(hits)} 条：{'、'.join(hits[:5])}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("written")
