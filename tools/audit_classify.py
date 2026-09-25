# -*- coding: utf-8 -*-
"""质量审计 B：分类一致性——找出「标签和条目本身矛盾」的条目。

判定只看条目自身（名称/说明/入口字段/网址），不看章节名，因为章节污染正是问题来源之一：
  · 校区：翔安/漳州/马来西亚 专属条目，但名称与说明里都没有该校区字样，网址也不像校区专属
  · 用途：机构/学院门户被标成 生活/学习/办事；工具类被标成 资讯
  · 对象：无任何身份线索却标了 研究生/本科生/教师/校友/访客
  · 形态：标了小程序却没提微信；标了网站系统但网址是 /info/ 文章页（应是说明页）

用法：python tools/audit_classify.py  → data/_classify_audit.txt
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "portal.json"
OUT = ROOT / "data" / "_classify_audit.txt"

CAMPUS_HINT = {
    "翔安校区": ("翔安", "xaxq", "xah"),
    "漳州校区": ("漳州", "zzxq", "xujc", "jgxy", "嘉庚"),
    "马来西亚分校": ("马来西亚", "xmu.edu.my", "my.xmu"),
    "思明校区": ("思明", "本部", "海韵"),
}
ORG_SUFFIX = ("学院", "学部", "学系", "研究院", "研究所", "中心", "实验室", "处", "部",
              "办公室", "管委会", "工会", "团委", "委员会", "图书馆", "博物馆", "档案馆",
              "医院", "集团", "总会", "秘书处", "基金会", "校友会", "大学", "系")
LIFE_WORDS = ("宿舍", "食堂", "水", "电", "洗", "淋浴", "热水", "超市", "快递", "班车",
              "理发", "就医", "医院", "报修", "公寓", "洗衣", "空调", "网络")
STUDY_WORDS = ("课程", "选课", "成绩", "考试", "教务", "图书", "借阅", "论文", "学位",
               "培养", "教学", "课堂", "讲座", "数据库", "文献", "自习")
WORK_WORDS = ("系统", "平台", "门户", "大厅", "办理", "申请", "预约", "查询", "缴费",
              "报修", "登记", "审批", "打印", "证明", "服务")
AUDIENCE_HINT = {
    "研究生": ("研究生", "硕士", "博士", "学位", "导师"),
    "本科生": ("本科", "选课", "四六级", "学籍"),
    "教师": ("教师", "教工", "教职工", "职称", "科研", "人事"),
    "校友": ("校友",),
    "访客/公众": ("访客", "参观", "公众", "进校", "入校"),
}


def main() -> None:
    items = json.loads(DATA.read_text(encoding="utf-8"))["items"]
    problems: list[str] = []
    counts = {"campus": 0, "purpose": 0, "audience": 0, "kind": 0}

    for it in items:
        name, desc, url = it["name"], it.get("desc") or "", it.get("url") or ""
        hay = f"{name} {desc} {url}"
        issues = []

        # 校区
        for campus, hints in CAMPUS_HINT.items():
            if campus in (it.get("campus") or []):
                if not any(h.lower() in hay.lower() for h in hints):
                    issues.append(f"校区={campus} 但名称/说明/网址都没有该校区线索")
        # 用途
        purpose = it.get("purpose") or []
        is_org = re.sub(r"（[^）]*）", "", name).strip().endswith(ORG_SUFFIX)
        if is_org and ({"生活", "学习", "办事"} & set(purpose)):
            issues.append(f"机构门户（{name}）却标了用途 {'/'.join(purpose)}")
        if "生活" in purpose and not any(w in hay for w in LIFE_WORDS):
            issues.append("用途=生活，但没有任何生活类关键词")
        if "学习" in purpose and not any(w in hay for w in STUDY_WORDS):
            issues.append("用途=学习，但没有任何学习类关键词")
        if "办事" in purpose and not any(w in hay for w in WORK_WORDS) and not is_org:
            issues.append("用途=办事，但看不出能办什么事")
        # 对象
        for who, hints in AUDIENCE_HINT.items():
            if who in (it.get("audience") or []) and not any(h in hay for h in hints):
                issues.append(f"对象={who}，但没有任何相关线索")
        # 形态
        if it.get("kind") == "miniprogram" and "小程序" not in hay and "微信" not in hay:
            issues.append("形态=微信小程序，但名称/说明都没提小程序")
        if it.get("kind") == "web" and re.search(r"/info/\d+/\d+\.htm|/\d{4}/\d{4}/", url):
            issues.append("形态=网站/系统，但网址是文章页（应属说明/公告类）")

        if issues:
            counts["campus" if any(i.startswith("校区") for i in issues) else "purpose"] += 1
            problems.append(f"· {name}\n    标签：校区={'/'.join(it.get('campus') or [])} "
                            f"对象={'/'.join(it.get('audience') or [])} "
                            f"用途={'/'.join(purpose)} 形态={it.get('kind')} 端={it.get('platform')}\n"
                            f"    问题：{'；'.join(issues)}\n"
                            f"    说明：{desc[:70]}\n    网址：{url or '（无）'}")

    OUT.write_text(
        f"条目总数 {len(items)}｜疑似分类问题 {len(problems)} 条\n\n" + "\n".join(problems),
        encoding="utf-8",
    )
    print(f"疑似分类问题 {len(problems)} / {len(items)} → {OUT.name}")


if __name__ == "__main__":
    main()
