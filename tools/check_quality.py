# -*- coding: utf-8 -*-
"""质量闸门：目录里出现"牛头不对马嘴"的说明或标签时直接报错（可接进构建流程）。

检查项：
  1. 废话模板：说明等于或包含已知的空话（"部门职责、办事流程、表格下载…""厦门大学在线服务入口"…）
  2. 可疑字串：厦门大学二 / TODO / 待补 / 厦门大学8.6 …
  3. 张冠李戴：不同网址、不同名字的条目共用同一条说明
  4. 标签与形态矛盾：机构门户标了 生活/学习/办事（除了人工钉死的例外）；小程序条目没提微信
  5. 短说明（<10 字）与缺说明
用法：python tools/check_quality.py   （非 0 退出码 = 不合格）
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "portal.json"
sys.path.insert(0, str(ROOT / "tools"))
import build_data  # noqa: E402  （复用同一份人工例外表，避免两处定义打架）

# 人工钉死过用途的条目不算"机构门户标业务用途"
EXEMPT = set(build_data.NATURE_OVERRIDES) | set(build_data.OVERRIDES) | set(build_data.UNIT_DESC)

BOILERPLATE = (
    "部门职责、办事流程、表格下载与通知公告",
    "厦门大学在线服务入口",
    "官方入口。",
    "相关入口。",
    "待补充",
    "暂无简介",
)
SUSPECT = ("厦门大学二", "TODO", "待补", "厦门大学8.6", "xxx", "XXX")
ORG_SUFFIX = ("学院", "学部", "学系", "研究院", "研究所", "研究中心", "实验室", "处", "部",
              "办公室", "管委会", "工会", "团委", "委员会", "图书馆", "博物馆", "档案馆",
              "医院", "集团", "总会", "秘书处", "基金会", "校友会", "中心", "编辑部")


def main() -> int:
    items = json.loads(DATA.read_text(encoding="utf-8"))["items"]
    problems: list[str] = []

    for it in items:
        name, desc = it["name"], it.get("desc") or ""
        for word in BOILERPLATE:
            if word in desc:
                problems.append(f"[废话模板] {name}：{desc[:60]}")
        for word in SUSPECT:
            if word in desc or word in name:
                problems.append(f"[可疑字串] {name}：{desc[:60]}")

    # 同说明不同条目
    by_desc: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        if it.get("desc"):
            by_desc[it["desc"]].append(it)
    for desc, group in by_desc.items():
        urls = {it.get("url") or it["name"] for it in group}
        if len(group) > 1 and len(urls) > 1:
            problems.append(f"[一条说明多处用] {len(group)} 条：{desc[:50]} → "
                            f"{'、'.join(it['name'] for it in group)}")

    for it in items:
        name = re.sub(r"（[^）]*）", "", it["name"]).strip()
        if (name.endswith(ORG_SUFFIX) and it["name"] not in EXEMPT
                and ({"生活", "学习", "办事"} & set(it.get("purpose") or []))):
            problems.append(f"[机构门户标了业务用途] {it['name']}：{'/'.join(it['purpose'])}"
                            f"（机构门户应为 资讯/科研；确属例外请写进 NATURE_OVERRIDES）")
        # 小程序条目至少要能找到：要么有网址，要么有微信里怎么找的提示
        if it.get("kind") == "miniprogram" and not it.get("url") and not it.get("entry"):
            problems.append(f"[小程序无法找到] {it['name']}：既没有网址也没有入口提示")
        desc = it.get("desc") or ""
        if not desc.strip():
            problems.append(f"[缺说明] {it['name']}")
        elif len(desc) < 10:
            problems.append(f"[说明过短] {it['name']}：{desc}")

    print(f"条目 {len(items)}｜问题 {len(problems)}")
    for line in problems:
        print("  " + line)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
