# -*- coding: utf-8 -*-
"""手机端网址（首页那一块）后端自检。

查四件事：
  1. app.py 里的 MOBILE_SITE 是个合法的 https 地址
  2. /api/ping 会把它给前端（前端不写死网址，换部署只改 app.py）
  3. /api/open 放行这个网址（否则点"在浏览器打开"会被白名单拒绝）
  4. 白名单没被放宽：目录外的任意网址照样拒绝

浏览器不会被真的打开——把 open_in_browser 换成桩函数再发请求。
加 --live 才会联网确认这个网址当前能打开（默认离线跑）。

用法：python tools/check_mobile_url.py [--live]
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def http(url: str, payload: dict | None = None, timeout: float = 8.0):
    """返回 (状态码, 解析后的 JSON)"""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except ValueError:
            return exc.code, {"raw": body[:200]}


def main() -> int:
    live = "--live" in sys.argv
    bad = 0
    url = app.MOBILE_SITE
    print("== 1. 配置 ==")
    print("  MOBILE_SITE = %s" % url)
    if not url.startswith("https://"):
        print("  不是 https 地址（手机加到主屏必须是 https）")
        bad += 1
    if not url.endswith("/"):
        print("  建议以 / 结尾，复制给别人更规整")
        bad += 1

    opened: list[str] = []
    app.open_in_browser = lambda u: opened.append(u)   # 桩：不真的开浏览器

    # main() 里是这么挂上去的，这里照做（Handler 通过 self.catalog 取目录）
    app.Handler.catalog = app.Catalog()
    app.Handler.userdata = app.UserData()

    server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % port
    try:
        print("\n== 2. /api/ping 把网址给前端 ==")
        status, body = http(base + "/api/ping")
        got = str(body.get("mobile", ""))
        print("  HTTP %s｜items=%s｜mobile=%s" % (status, body.get("items"), got))
        if status != 200 or got != url:
            print("  /api/ping 没给出正确的手机端网址")
            bad += 1

        print("\n== 3. /api/open 放行这个网址 ==")
        status, body = http(base + "/api/open", {"url": url})
        print("  HTTP %s｜%s" % (status, body))
        if status != 200 or not body.get("ok") or opened != [url]:
            print("  没能通过 /api/open 打开（前端「在浏览器打开」按钮会失败）")
            bad += 1

        print("\n== 4. 白名单没被放宽 ==")
        status, body = http(base + "/api/open", {"url": "https://example.com/"})
        print("  HTTP %s｜%s" % (status, body))
        if status != 400 or body.get("ok"):
            print("  目录外地址竟然被放行了")
            bad += 1
        # 同一个站点的其他路径也不该放行（只放行这一个地址）
        status, body = http(base + "/api/open", {"url": url + "evil"})
        print("  带尾巴的变体 HTTP %s｜%s" % (status, body.get("error", body)))
        if status == 200:
            print("  变体被误放行")
            bad += 1
    finally:
        server.shutdown()
        server.server_close()

    if live:
        print("\n== 5. 联网确认（--live）==")
        for path in ("/", "/portal.json"):
            try:
                with urllib.request.urlopen(
                        urllib.request.Request(url.rstrip("/") + path,
                                               headers={"User-Agent": "Mozilla/5.0"}),
                        timeout=20) as resp:
                    raw = resp.read()
                extra = ""
                if path.endswith("portal.json"):
                    items = len(json.loads(raw.decode("utf-8")).get("items", []))
                    extra = "｜条目 %d" % items
                    if items < 300:
                        print("  线上数据看起来不完整%s" % extra)
                        bad += 1
                print("  %s → HTTP %s｜%d 字节%s" % (path, resp.status, len(raw), extra))
            except Exception as exc:  # noqa: BLE001
                print("  %s 打不开：%s" % (path, exc))
                bad += 1

    print("\n结果：%s" % ("全部通过" if not bad else "%d 处问题" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
