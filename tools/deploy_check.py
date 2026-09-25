# -*- coding: utf-8 -*-
"""部署验收：给一个公网网址，逐项检查"这套软件"是不是真的跑起来了。

用法：
    python tools/deploy_check.py https://你的网址/
    python tools/deploy_check.py https://你的网址/ --deep     # 额外抓取页面里引用的资源

检查项：
  1. index.html 能打开、标题正确、og 分享卡片齐全（微信里发链接才有像样的卡片）
  2. portal.json 能打开、是合法 JSON、条目数与本地一致
  3. manifest / sw.js / 分享图 / 图标 都在（PWA 与分享卡片的依赖）
  3b. 浏览器到底认不认这个 PWA：manifest 的 MIME 类型、192/512 图标、Service Worker
  4. 是否 https（只有 https 才能"添加到主屏幕"，Service Worker 也只在 https 下工作）
  5. 页面引用的 css/js/图标是否都能取到

第 3b 组是踩坑后补上的：Netlify 把 .webmanifest 当 application/octet-stream 发，
浏览器据此判定 manifest 无效，"添加到主屏幕"直接不可用——这类问题必须自动查出来。
"""
from __future__ import annotations

import hashlib
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")}

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def fetch(url: str, timeout: int = 25) -> tuple[int, bytes, dict]:
    """返回 (状态码, 内容, 响应头)。响应头的键统一转小写，避免大小写踩坑。"""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                    timeout=timeout, context=CTX) as resp:
            return resp.status, resp.read(), {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), {k.lower(): v for k, v in (exc.headers or {}).items()}
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc).encode(), {}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    base = sys.argv[1].strip()
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    if not base.endswith("/"):
        base += "/"
    deep = "--deep" in sys.argv

    print(f"检查 {base}\n")

    print("1) 首页")
    status, body, headers = fetch(base)
    html = body.decode("utf-8", "ignore")
    record("index.html 能打开", status == 200, f"HTTP {status}｜{len(body)} B")
    record("标题正确", "厦大统一门户" in html)
    for tag, why in (("og:title", "微信分享标题"), ("og:description", "分享描述"), ("og:image", "分享缩略图")):
        record(f"分享卡片 {tag}（{why}）", tag in html)

    print("\n2) 目录数据")
    status, body, _h = fetch(urllib.parse.urljoin(base, "portal.json"))
    local = json.loads((ROOT / "data" / "portal.json").read_text(encoding="utf-8"))
    try:
        remote = json.loads(body.decode("utf-8"))
        count = len(remote.get("items", []))
        record("portal.json 是合法 JSON 且有条目", count > 0,
               f"线上 {count} 条｜本地 {len(local['items'])} 条")
        record("条目数与本地一致", count == len(local["items"]),
               "一致" if count == len(local["items"]) else "线上是旧版本，记得重新部署")
    except Exception as exc:  # noqa: BLE001
        record("portal.json 能解析", False, f"HTTP {status}｜{type(exc).__name__}")

    print("\n2b) 传上去的到底是不是本地这一版（逐字节比）")
    build_dir = ROOT / "dist-mobile"
    for name in ("index.html", "app.js", "styles.css", "sw.js", "portal.json"):
        local_file = build_dir / name
        if not local_file.exists():
            record(f"{name} 本地产物存在", False, "先跑 python tools/build_mobile.py")
            continue
        status, body, _h = fetch(urllib.parse.urljoin(base, name))
        live = hashlib.sha256(body).hexdigest()[:12] if status == 200 else "（取不到）"
        mine = hashlib.sha256(local_file.read_bytes()).hexdigest()[:12]
        record(f"{name} 与本地一致", live == mine,
               f"线上 {live}｜本地 {mine}" + ("" if live == mine else "　← 传的是旧版本，重新拖一次 dist-mobile"))

    print("\n3) PWA 与分享素材")
    for path, name in (("manifest.json", "PWA 清单"),
                       ("sw.js", "Service Worker"),
                       ("assets/logo/share-card.png", "分享缩略图"),
                       ("assets/logo/logo-192.png", "主屏图标 192"),
                       ("assets/logo/logo-512.png", "主屏图标 512")):
        status, body, headers = fetch(urllib.parse.urljoin(base, path))
        record(f"{name}（{path}）", status == 200,
               f"HTTP {status}｜{len(body)} B｜{headers.get('content-type', '')[:32]}")

    print("\n3b) 浏览器到底认不认这个 PWA（能装到主屏的硬条件）")
    status, body, headers = fetch(urllib.parse.urljoin(base, "manifest.json"))
    ctype = (headers.get("content-type") or "").split(";")[0].strip().lower()
    record("manifest 用的是 JSON 类型的 Content-Type",
           ctype in ("application/manifest+json", "application/json", "text/json"),
           f"{ctype or '（没读到）'}——如果是 application/octet-stream，浏览器会判定 manifest 无效、不给安装")
    try:
        manifest = json.loads(body.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        manifest = {}
        record("manifest 能解析", False, str(exc))
    if manifest:
        record("manifest 有 name / short_name",
               bool(manifest.get("name") and manifest.get("short_name")))
        record("manifest 有 start_url", bool(manifest.get("start_url")))
        record("display 是 standalone / fullscreen / minimal-ui",
               manifest.get("display") in ("standalone", "fullscreen", "minimal-ui"),
               str(manifest.get("display")))
        sizes = {i.get("sizes") for i in manifest.get("icons", [])}
        record("图标含 Chrome 要求的 192px", "192x192" in sizes, "、".join(sorted(s for s in sizes if s)))
        record("图标含 512px", "512x512" in sizes)
        for icon in manifest.get("icons", []):
            if icon.get("sizes") not in ("192x192", "512x512"):
                continue
            st, bd, _h = fetch(urllib.parse.urljoin(base, icon["src"]))
            record(f"  图标可访问 {icon['src']}（{icon['sizes']}）", st == 200 and len(bd) > 500,
                   f"HTTP {st}｜{len(bd)} B")
    st, bd, _h = fetch(urllib.parse.urljoin(base, "sw.js"))
    record("Service Worker 可访问（安装条件之一）", st == 200 and b"fetch" in bd, f"HTTP {st}")

    print("\n4) https 与缓存头")
    record("是 https（能装到主屏）", base.startswith("https://"),
           "http 也能用，但浏览器不允许添加到主屏幕" if base.startswith("http://") else "")
    status, _b, headers = fetch(urllib.parse.urljoin(base, "portal.json"))
    cc = headers.get("cache-control", "")
    record("portal.json 没被长时间缓存", "no-cache" in cc or "max-age=0" in cc, cc or "（没读到）")

    if deep:
        print("\n5) 页面引用的资源")
        for ref in sorted(set(re.findall(r'(?:src|href)="([^"#:]+)"', html))):
            if ref.startswith(("http", "//", "data:")):
                continue
            status, body, _h = fetch(urllib.parse.urljoin(base, ref))
            record(f"  {ref}", status == 200, f"HTTP {status}｜{len(body)} B")

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n结果：{len(results) - len(failed)}/{len(results)} 通过")
    if failed:
        print("未通过：" + "；".join(failed))
        return 1
    print("这套软件已经跑在公网上了 —— 手机浏览器打开这个网址即可，「添加到主屏幕」后就像 App。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
