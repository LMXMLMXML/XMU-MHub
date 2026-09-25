# -*- coding: utf-8 -*-
"""质量审计 A：逐条访问网址，把「页面标题」和「条目名称」对不上、或打不开的条目揪出来。

- 只读 GET，8 线程，单条 8 秒超时，失败重试一次
- 标题与条目名的字符重合度低 → 疑似"牛头不对马嘴"（链接挂错 / 描述写错）
- 非 200 / 超时 / TLS 失败 → 死链或需要校园网的入口

用法：python tools/audit_links.py            # 全量
      python tools/audit_links.py 40         # 只查前 40 条（快速抽检）
输出：data/_links_audit.txt（明细）、data/_links_mismatch.txt（可疑清单）
"""
from __future__ import annotations

import datetime
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "portal.json"
DETAIL = ROOT / "data" / "_links_audit.txt"
SUSPECT = ROOT / "data" / "_links_mismatch.txt"
STATUS = ROOT / "data" / "link_status.json"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
# 只剔除"体裁词"，**不能**把"厦门大学"也剔掉——否则所有标题的相似度都会变成 0
GENRE = set("官网首页入口系统平台服务指南说明中心网站欢迎来到登录页正文栏目"
            " -_|·|，。,:：()（）[]【】")


def chars(text: str) -> set[str]:
    return {c for c in text if c not in GENRE and not c.isspace()}


def fetch(url: str) -> tuple[int, str, str]:
    """返回 (状态码, 标题, 备注)。0 表示异常。"""
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=8, context=CTX) as resp:
                raw = resp.read(40000)
                charset = resp.headers.get_content_charset() or "utf-8"
                html = raw.decode(charset, "ignore")
                title = TITLE_RE.search(html)
                text = re.sub(r"\s+", " ", title.group(1)).strip() if title else ""
                return resp.status, text[:90], ""
        except urllib.error.HTTPError as exc:
            if attempt == 1:
                return exc.code, "", f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            if attempt == 1:
                return 0, "", type(exc).__name__
    return 0, "", "失败"


def similar(name: str, title: str) -> float:
    """条目名与页面标题的字符重合度（Dice 系数，0~1；无标题返回 -1）。"""
    if not title:
        return -1.0
    a, b = chars(name), chars(title)
    if not a or not b:
        return -1.0
    return 2 * len(a & b) / (len(a) + len(b))


def main() -> None:
    items = json.loads(DATA.read_text(encoding="utf-8"))["items"]
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(items)
    targets = [it for it in items if it.get("url")][:limit]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda it: (it, *fetch(it["url"])), targets))

    detail, suspects, dead = [], [], []
    for item, status, title, note in results:
        score = similar(item["name"], title)
        flag = ""
        if status != 200:
            flag = "死链/不可访问"
            dead.append(item)
        elif score < 0.5:
            flag = "标题与条目名不符"
            suspects.append((item, status, title, score))
        detail.append(f"[{status or note:>4}] 相似度{score:+.2f} {flag:<12} {item['name']}\n"
                      f"        标题：{title or '（无标题）'}\n        {item['url']}")

    DETAIL.write_text("\n".join(detail), encoding="utf-8")

    # 把探测结果写成 JSON，供 build_data 打到条目上（前端据此显示"实测打不开"提示）
    # 注意：similar 必须在这里现算——之前误用了上一个循环残留的 score，导致所有条目都是 0.00
    status_map = {
        item["name"]: {"status": status, "title": title, "note": note,
                       "similar": round(similar(item["name"], title), 2)}
        for item, status, title, note in results
    }
    status_map["_checked_at"] = datetime.date.today().isoformat()
    status_map["_total"] = len(targets)
    STATUS.write_text(json.dumps(status_map, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = [f"带网址条目 {len(targets)} 条｜打不开 {len(dead)} 条｜标题可疑 {len(suspects)} 条", ""]
    lines.append("== 打不开的条目 ==")
    for item in dead:
        lines.append(f"  · {item['name']}  {item['url']}")
    lines.append("")
    lines.append("== 标题与条目名对不上（疑似挂错链接 / 描述错位）==")
    for item, status, title, score in sorted(suspects, key=lambda x: x[3]):
        lines.append(f"  [{score:+.2f}] {item['name']}")
        lines.append(f"        实际标题：{title}")
        lines.append(f"        {item['url']}")
    SUSPECT.write_text("\n".join(lines), encoding="utf-8")
    print(f"打不开 {len(dead)}｜标题可疑 {len(suspects)}｜明细 {SUSPECT.name}")


if __name__ == "__main__":
    main()
