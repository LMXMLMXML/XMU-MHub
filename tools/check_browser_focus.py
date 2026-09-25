# -*- coding: utf-8 -*-
"""检查"点条目 → 浏览器窗口显示在软件前面"这套逻辑。

做三件事（默认都不会打扰你正在用的窗口）：
  1. 列出当前识别到的浏览器窗口，确认枚举逻辑认得出来
  2. 确认软件自己的窗口会被排除（否则"提到前面"的会变成软件自己）
  3. 用无效句柄调一遍 raise_window，确认不会崩

加 --open 才会真的开一个标签页做端到端验证（会在你的浏览器里多出一个标签，用完自己关掉）：
    python tools/check_browser_focus.py --open https://www.xmu.edu.cn
"""
from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app  # noqa: E402


def titles(handles: list[int]) -> list[str]:
    user32 = ctypes.WinDLL("user32")
    out = []
    for hwnd in handles:
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        out.append(buf.value)
    return out


def main() -> int:
    if sys.platform != "win32":
        print("这套逻辑只对 Windows 有意义，当前系统跳过。")
        return 0

    print("1) 枚举浏览器窗口")
    wins = app.browser_windows()
    print(f"   识别到 {len(wins)} 个")
    for hwnd, title in zip(wins, titles(wins)):
        print(f"     {hwnd}｜{title[:70]}")

    print("\n2) 软件自己的窗口必须被排除")
    probe = f"{app.APP_WINDOW_TITLE} · 厦门大学信息学院"
    print(f"   排除前缀：{app.APP_WINDOW_TITLE!r}")
    print(f"   软件窗口标题 {probe!r} 会被排除：{probe.startswith(app.APP_WINDOW_TITLE)}")
    print(f"   当前识别结果里含有软件窗口：{any(t.startswith(app.APP_WINDOW_TITLE) for t in titles(wins))}（应为 False）")

    print("\n3) 异常输入不能把程序搞崩")
    for bad in (0, 12345, -1):
        print(f"   raise_window({bad}) -> {app.raise_window(bad)}（应为 False，不抛异常）")

    print("\n4) focus_browser 的三种判断（用假的窗口列表跑，不碰你正在用的窗口）")
    raised: list[int] = []
    real_windows, real_fg, real_raise = app.browser_windows, app._foreground_window, app.raise_window
    app.raise_window = lambda hwnd: (raised.append(hwnd), True)[1]
    try:
        # 情况一：浏览器已经在前台 → 不该去动它
        app.browser_windows = lambda: [111]
        app._foreground_window = lambda: 111
        raised.clear()
        app.focus_browser([111], timeout=1.0)
        print(f"   浏览器已在前台 → 提窗口次数 {len(raised)}（应为 0）")

        # 情况二：冒出了新窗口 → 提新的那个
        app.browser_windows = lambda: [222, 111]
        app._foreground_window = lambda: 999
        raised.clear()
        app.focus_browser([111], timeout=3.0)
        print(f"   出现新窗口 → 提了 {raised}（应为 [222]）")

        # 情况三：老窗口只是加了个标签 → 等一会儿再提它
        app.browser_windows = lambda: [111]
        app._foreground_window = lambda: 999
        raised.clear()
        app.focus_browser([111], timeout=4.0)
        print(f"   只有老窗口 → 提了 {raised}（应为 [111]）")
    finally:
        app.browser_windows, app._foreground_window, app.raise_window = real_windows, real_fg, real_raise

    print("\n5) 快照必须拍在「打开之前」（拍晚了新窗口会被当成旧窗口）")
    order: list = []
    real_snap, real_open, real_focus = app.browser_windows, app.webbrowser.open, app.focus_browser
    app.browser_windows = lambda: (order.append("snapshot"), [111])[1]
    app.webbrowser.open = lambda u: order.append(("open", u))
    app.focus_browser = lambda before, timeout=8.0: order.append(("focus", list(before)))
    try:
        app.open_in_browser("https://example.com/")
        print(f"   调用顺序：{order}")
        ok = (order and order[0] == "snapshot"
              and order[1][0] == "open" and order[2] == ("focus", [111]))
        print(f"   顺序正确：{ok}（应为 True）")
    finally:
        app.browser_windows, app.webbrowser.open, app.focus_browser = real_snap, real_open, real_focus

    print("\n6) 走真实 HTTP 路由：POST /api/open 要拍快照 + 打开浏览器（浏览器调用被替换成假的）")
    import json
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer

    app.Handler.catalog = app.Catalog()
    app.Handler.userdata = app.UserData()          # 只读，不会写你的数据文件
    server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    events: list = []
    app.browser_windows = lambda: (events.append("snapshot"), [])[1]
    app.webbrowser.open = lambda u: events.append(("open", u))
    app.focus_browser = lambda before, timeout=8.0: events.append("focus")
    try:
        item = app.Handler.catalog.items[0]

        def post(payload: dict) -> tuple[int, dict]:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/open",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return resp.status, json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                return exc.code, json.loads(exc.read().decode("utf-8"))

        status, res = post({"id": item["id"]})
        time.sleep(0.4)
        good = (status == 200 and res.get("ok")
                and ("open", item["url"]) in events and "snapshot" in events)
        print(f"   收录条目「{item['name']}」→ HTTP {status}｜事件 {events}")
        print(f"   拍快照 + 打开 + 提窗口 都发生了：{good}（应为 True）")

        events.clear()
        status, res = post({"url": "https://www.baidu.com"})
        time.sleep(0.3)
        print(f"   目录外网址 → HTTP {status}｜事件 {events}")
        print(f"   目录外不该开浏览器：{not events}（应为 True）")
    finally:
        server.shutdown()

    if "--open" in sys.argv:
        index = sys.argv.index("--open")
        url = sys.argv[index + 1] if len(sys.argv) > index + 1 else "https://www.xmu.edu.cn"
        print(f"\n5) 端到端：打开 {url} 并等 8 秒，看它有没有到前台")
        before = app.browser_windows()
        print(f"   打开前的浏览器窗口：{before}")
        app.open_in_browser(url)
        for _ in range(16):
            time.sleep(0.5)
            fg = app._foreground_window()
            now = app.browser_windows()
            if fg in now:
                print(f"   ✔ 0.5 秒粒度观察：浏览器已在前台（句柄 {fg}）")
                return 0
        print("   ✘ 8 秒内没看到浏览器到前台——把这行结果发我")

    print("\n（没加 --open，所以没有真的开标签页）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
