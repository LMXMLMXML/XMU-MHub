# -*- coding: utf-8 -*-
"""统计《厦门大学网址总集.md》中出现的唯一 URL 数量（用于校正文档里的"共收录 N 个链接"）。

用法：python tools/count_urls.py
"""
from __future__ import annotations

import re
from pathlib import Path

DOC = Path(r"D:\AI\厦门大学网址总集.md")
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
