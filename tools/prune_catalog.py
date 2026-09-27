# -*- coding: utf-8 -*-
"""把已确认失效的条目从两份《总集》里删掉，让文档与目录保持一致。

名单来自 build_data.REMOVED_ENTRIES（人工确认过：DNS 无解析或页面确认 404）。
只删"名字能对上"的表格行，不动其它内容；跑完会提示还剩多少链接。

用法：python tools/prune_catalog.py            # 预览要删哪些行
      python tools/prune_catalog.py --apply    # 真正写入
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# --- 仓库根目录，随 clone 位置自适应（原来这里写死了 D:\AI\xmu_hub）---
ROOT = Path(__file__).resolve().parent.parent

# 两份《总集》不在仓库里，位置也不固定，沿父目录逐级向上找
def _find_doc(name: str) -> Path:
    for base in (ROOT, *ROOT.parents):
        cand = base / name
        if cand.exists():
            return cand
    raise SystemExit(
        f"[错误] 找不到源文档 {name}；请放在仓库根目录或它的任一级父目录下"
    )


DOCS = [_find_doc("厦门大学网址总集.md"), _find_doc("厦门大学微信小程序总集.md")]
sys.path.insert(0, str(ROOT / "tools"))
import build_data  # noqa: E402

TARGETS = set(build_data.REMOVED_ENTRIES)


def row_name(line: str) -> str:
    if not line.lstrip().startswith("|"):
        return ""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells[0].strip("*` ") if cells else ""


def main() -> None:
    apply = "--apply" in sys.argv
    total_removed = 0
    for doc in DOCS:
        text = doc.read_text(encoding="utf-8")
        kept, removed = [], []
        for line in text.splitlines():
            name = row_name(line)
            if name and name in TARGETS:
                removed.append(name)
                continue
            kept.append(line)
        # 该条目可能以"| 名字 | 网址 | 说明 |"出现，也可能出现在表格里多处
        if removed:
            doc.write_text("\n".join(kept) + "\n", encoding="utf-8") if apply else None
            print(f"{doc.name}: 删除 {len(removed)} 行 → {', '.join(sorted(set(removed)))}")
            total_removed += len(removed)
        else:
            print(f"{doc.name}: 没有匹配行")
    if not apply:
        print("\n（预览模式，未写入；加 --apply 才真正删除）")
    else:
        print(f"\n已删除 {total_removed} 行")


if __name__ == "__main__":
    main()
