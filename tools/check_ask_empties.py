# -*- coding: utf-8 -*-
"""看看 AI 问答在什么情况下会回"没有找到匹配的入口"（本地候选为空）。

用法：先启动后端，再 python tools/check_ask_empties.py
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT_FILE = ROOT / "data" / "_runtime_port.txt"

QUESTIONS = [
    "宿舍水管漏了找谁", "我是研究生，在哪里查成绩", "校友想进校看看要预约吗",
    "怎么入党", "有没有可以借教室的地方", "明天有课吗", "保研怎么弄",
    "食堂几点开门", "怎么申请助学贷款", "快递去哪儿拿",
    "sports", "help", "阿巴阿巴", "11111", "？？？",
    "今天天气怎么样", "帮我写一首诗", "python 怎么装库", "我想退学",
]


def main() -> int:
    port = PORT_FILE.read_text(encoding="utf-8").strip()
    base = f"http://127.0.0.1:{port}"
    empty = []
    for q in QUESTIONS:
        payload = json.dumps({"question": q}).encode("utf-8")
        req = urllib.request.Request(
            base + "/api/ask", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        answer = (data.get("answer") or "").replace("\n", " ")
        n = len(data.get("items") or [])
        is_empty = "没有找到匹配的入口" in answer or n == 0
        if is_empty:
            empty.append(q)
        print(f"{'❌' if is_empty else '  '} 「{q}」→ items={n}｜{answer[:70]}")
    print(f"\n回『没有找到匹配的入口』的问题：{len(empty)} / {len(QUESTIONS)} -> {empty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
