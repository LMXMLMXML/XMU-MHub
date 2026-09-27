# -*- coding: utf-8 -*-
"""统计《厦门大学网址总集.md》中出现的唯一 URL 数量（用于校正文档里的"共收录 N 个链接"）。

用法：python tools/count_urls.py
"""
from __future__ import annotations

import re
from pathlib import Path


# --- 仓库根目录，随 clone 位置自适应（原来这里写死了 D:\AI\xmu_hub）---
ROOT = Path(__file__).resolve().parent.parent


def _find_doc(name: str) -> Path:
    """源《总集》不在仓库里，位置不固定，沿父目录逐级向上找。"""
    for base in (ROOT, *ROOT.parents):
        cand = base / name
        if cand.exists():
            return cand
    raise SystemExit(
        f"[错误] 找不到源文档 {name}；请放在仓库根目录或它的任一级父目录下"
    )


DOC = _find_doc("厦门大学网址总集.md")
PATTERN = re.compile(r"https?://[^\s|)）】\]]+")


def main() -> None:
    text = DOC.read_text(encoding="utf-8")
    urls = {u.rstrip(".,，。;；") for u in PATTERN.findall(text)}
    print(f"唯一 URL 数：{len(urls)}")
    hosts = {}
    for u in urls:
        host = u.split("//", 1)[1].split("/", 1)[0]
        hosts[host] = hosts.get(host, 0) + 1
    top = sorted(hosts.items(), key=lambda kv: -kv[1])[:12]
    print("出现最多的域名：")
    for host, count in top:
        print(f"  {host}: {count}")
    xmu = {h for h in hosts if h.endswith("xmu.edu.cn") or h.endswith("xmu.edu.my")}
    other = set(hosts) - xmu
    print(f"其中 xmu 体系域名 {len(xmu)} 个、其它官方/第三方域名 {len(other)} 个")
    print("其它域名：" + "、".join(sorted(other)))


if __name__ == "__main__":
    main()
