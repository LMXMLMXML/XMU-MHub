# -*- coding: utf-8 -*-
"""精查"打不开"的条目：区分「域名没了/页面 404」与「只是拦我/要校园网」。

判定方式（逐条多种尝试）：
  1. DNS 解析：解析不到 → 域名已不存在（真死）
  2. https 与 http 各试一次，浏览器 UA + 15s 超时
  3. 分类：域名不存在 / 确认 404·410 / 403·401（被拦，站还活着）/ 超时 / 连接被拒 / SSL 问题

用法：python tools/probe_dead.py → data/_dead_probe.txt
"""
from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "portal.json"
OUT = ROOT / "data" / "_dead_probe.txt"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def dns_ok(host: str) -> bool:
    try:
        socket.getaddrinfo(host, None)
        return True
    except OSError:
        return False


def try_url(url: str) -> tuple[int, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=15, context=CTX) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as exc:
        return exc.code, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return 0, type(exc).__name__


def probe(item: dict) -> tuple[str, str, str]:
    url = item.get("url") or ""
    host = urlparse(url).hostname or ""
    if not host:
        return item["name"], "无网址", "跳过"
    if not dns_ok(host):
        return item["name"], "域名不存在", f"{host} 解析失败"

    variants = [url]
    if url.startswith("http://"):
        variants.insert(0, "https://" + url[len("http://"):])
    elif url.startswith("https://"):
        variants.append("http://" + url[len("https://"):])

    last = ""
    for candidate in variants:
        status, note = try_url(candidate)
        last = f"{candidate} → {status or note}"
        if status == 200:
            return item["name"], "其实能打开", last
        if status in (401, 403):
            return item["name"], "被拦（站还活着）", last
        if status in (404, 410):
            return item["name"], "页面不存在", last
        if status == 0 and note in ("URLError", "timeout", "TimeoutError", "ConnectionResetError"):
            continue
    return item["name"], "连不上/超时", last


def main() -> None:
    items = json.loads(DATA.read_text(encoding="utf-8"))["items"]
    dead = [it for it in items if it.get("linkOk") is False]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(probe, dead))

    groups: dict[str, list[tuple[str, str]]] = {}
    for name, verdict, detail in results:
        groups.setdefault(verdict, []).append((name, detail))

    lines = [f"实测打不开的条目 {len(dead)} 条，精查结果：", ""]
    for verdict in ["域名不存在", "页面不存在", "被拦（站还活着）", "连不上/超时", "其实能打开", "无网址"]:
        rows = groups.get(verdict, [])
        if not rows:
            continue
        lines.append(f"== {verdict}（{len(rows)} 条）==")
        for name, detail in sorted(rows):
            lines.append(f"  · {name}\n      {detail}")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    for verdict, rows in groups.items():
        print(f"{verdict}: {len(rows)}")
    print(f"明细 → {OUT.name}")


if __name__ == "__main__":
    main()
