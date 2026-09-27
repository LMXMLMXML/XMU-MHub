"""校验 COVERAGE.md 里点名的每个入口，在 portal.json 中真实存在。

用途：覆盖度清单不能自说自话——写了"已覆盖 XX"，就得能在软件里搜到 XX。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# --- 仓库根目录，随 clone 位置自适应（原来这里写死了 D:\AI\xmu_hub）---
ROOT = Path(__file__).resolve().parent.parent


PORTAL = ROOT / "data" / "portal.json"
DOC = ROOT / "COVERAGE.md"
OUT = ROOT / "data" / "_coverage_audit.txt"

items = json.loads(PORTAL.read_text(encoding="utf-8"))["items"]
names = {i["name"] for i in items}
# 模糊匹配用：去掉括号与空白后的核心名
normalized = {}
for n in names:
    key = re.sub(r"[（()）\s·/]", "", n)
    normalized.setdefault(key, n)

NOISE = ("—", "无", "线下经营")


def split_outside_parens(text: str) -> list[str]:
    """按 、/，拆分，但不拆括号内的内容（如"后勤集团（报修、公寓、班车）"要整体保留）。"""
    out: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in text:
        if ch in "（(":
            depth += 1
        elif ch in "）)":
            depth = max(0, depth - 1)
        if depth == 0 and ch in "、，,／/":
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return out


def tokens_of(cell: str) -> list[str]:
    cell = cell.replace("**", "").strip()
    cell = re.sub(r"\s*等\s*\d+\s*家.*$", "", cell)   # 去掉"等 11 家"这类
    out = []
    for p in split_outside_parens(cell):
        p = re.sub(r"^等\s*", "", p.strip().strip("。;；"))
        if not p or len(p) < 2 or p in NOISE:
            continue
        if re.fullmatch(r"[\d\s家个人]+", p):
            continue
        if any(n in p for n in NOISE):
            continue
        out.append(p)
    return out


lines: list[str] = [f"目录条目数：{len(items)}", ""]
checked = matched = 0
misses: list[tuple[str, str]] = []

ENTRY_HEADERS = ("对应入口", "收录的入口", "入口")
entries_col = 2          # 默认第 3 列是入口列；遇到表头会重新定位
header_width = 0         # 表头列数，用于识别"表被另一张表截断"的情况
skipped_rows = 0

for raw in DOC.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line.startswith("|") or set(line) <= set("|-: "):
        continue
    cells = [c.strip() for c in line.strip("|").split("|")]
    if len(cells) < 2:
        continue

    # 表头行：记住入口列位置与表格宽度（清单里存在 3 列与 4 列两种表格）
    header_hit = next((i for i, c in enumerate(cells) if c in ENTRY_HEADERS), None)
    if header_hit is not None:
        entries_col = header_hit
        header_width = len(cells)
        continue

    # 列数与表头不一致 → 说明当前行不属于这张表，跳过以免错读列
    if header_width and len(cells) != header_width:
        skipped_rows += 1
        continue
    if len(cells) <= entries_col:
        skipped_rows += 1
        continue
    scene, status, entries = cells[0], cells[1] if len(cells) > 1 else "", cells[entries_col]
    if scene in ("场景", "—", "校区 / 单位") or "场景" in scene:
        continue
    if "❌" in status:
        continue
    for token in tokens_of(entries):
        checked += 1
        if token in names:
            matched += 1
            continue
        key = re.sub(r"[（()）\s·/]", "", token)
        if key in normalized:
            matched += 1
            continue
        hit = next((n for n in names if token in n or n in token), None)
        if hit:
            matched += 1
            continue
        misses.append((scene, token))

lines.append(f"校验入口名：{checked} 个，命中 {matched} 个，未命中 {len(misses)} 个")
lines.append(f"（入口列按表头自动识别；跳过列数不足的行 {skipped_rows} 行）")
lines.append("")
if misses:
    lines.append("=== 未命中的名字（清单里写了但目录中搜不到）===")
    for scene, token in misses:
        lines.append(f"  ❌ [{scene}] {token}")
else:
    lines.append("✅ 清单点名的入口全部能在目录中搜到")

lines.append("")
lines.append("=== 各状态条目数 ===")
for mark, label in (("✅", "已覆盖"), ("🟡", "部分覆盖"), ("❌", "官方无渠道")):
    lines.append(f"  {label}: {DOC.read_text(encoding='utf-8').count(mark)} 处")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines[:4]))
