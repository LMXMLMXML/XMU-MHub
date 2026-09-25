# -*- coding: utf-8 -*-
"""手机上预览静态版：在本机起一个静态服务器，并打印局域网地址。

用法：
    python tools/preview_mobile.py            # 默认 8080 端口
    python tools/preview_mobile.py 9000

先在 PC 上跑起来，然后手机连**同一个 WiFi**，浏览器打开打印出来的
http://<本机IP>:<端口>/ ，就能看到手机上的真实样子。

⚠️ 关于"像 App 一样打开"：浏览器只允许在 **https** 下把网页装到主屏
（Service Worker 也只在 https / localhost 下才工作）。局域网 http 能满足
看界面、搜索、筛选、收藏、本地检索，但装不了、也离线不了。
要真的装到主屏，把这个目录传到任意 https 静态空间，或者用内网穿透拿一个临时 https 地址：

    cloudflared tunnel --url http://localhost:8080      # 需要先装 cloudflared
    npx localtunnel --port 8080                         # 需要 Node

拿到 https://xxx.… 之后用手机打开那个地址，就能"添加到主屏幕"了。
"""
from __future__ import annotations

import http.server
import shutil
import socket
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOBILE = ROOT / "dist-mobile"


def lan_ip() -> str:
    """拿本机在局域网里的地址（不会真的发数据，只是让系统选出出口网卡）。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:  # noqa: BLE001
        return "127.0.0.1"
    finally:
        sock.close()


class Handler(http.server.SimpleHTTPRequestHandler):
    """带一点缓存头：portal.json 每次都问服务器，其余静态资源可以缓存。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(MOBILE), **kwargs)

    def end_headers(self):
        if self.path.endswith("portal.json"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))


def main() -> int:
    if not (MOBILE / "index.html").exists():
        print("还没有 dist-mobile，请先运行：python tools/build_mobile.py")
        return 1
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", port), Handler) as httpd:
        ip = lan_ip()
        print("手机版预览已启动（Ctrl+C 退出）")
        print(f"  电脑上打开：http://127.0.0.1:{port}/")
        print(f"  手机上打开：http://{ip}:{port}/     ← 手机要和电脑连同一个 WiFi")
        print()
        print("  提示：局域网是 http，能看能用，但浏览器不允许在这个地址上"
              "「添加到主屏幕」。")
        print("  想真的装到主屏，用下面任一种方式拿一个 https 地址：")
        for tool, cmd in (("cloudflared", f"cloudflared tunnel --url http://localhost:{port}"),
                          ("Node/npx", f"npx localtunnel --port {port}")):
            hint = "（已安装）" if shutil.which(tool.split("/")[0]) else "（没检测到，需先安装）"
            print(f"    {tool:12} {cmd}   {hint}")
        print("  或者把 dist-mobile/ 传到任意 https 静态空间（GitHub Pages / 对象存储 / 校内服务器）")
        print()
        threading.Timer(0.6, lambda: webbrowser.open(f"http://127.0.0.1:{port}/")).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已退出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
