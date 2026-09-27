# -*- coding: utf-8 -*-
"""打包版冒烟测试：直接打打包后的绿色版 exe（读它自己写的端口文件）。

用法：先启动 dist\\厦大统一门户-绿色版\\厦大统一门户-绿色版.exe --no-window，再运行本脚本。
检查：条目数、role 分布、facets.role、/api/history 记录与清空、前端是否含新特性标记。
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path


for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")   # 控制台默认 GBK，✔/✘ 会炸
    except Exception:
        pass

# --- 仓库根目录，随 clone 位置自适应（原来这里写死了 D:\AI\xmu_hub）---
ROOT = Path(__file__).resolve().parent.parent


EXE_DIR = ROOT / "dist" / "厦大统一门户-绿色版"
PORT_FILE = EXE_DIR / "data" / "_runtime_port.txt"


def post(base: str, path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base + path, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    port = PORT_FILE.read_text(encoding="utf-8").strip()
    base = f"http://127.0.0.1:{port}"
    catalog = json.loads(urllib.request.urlopen(base + "/api/catalog", timeout=15).read().decode("utf-8"))
    items = catalog["items"]
    roles = {}
    for item in items:
        roles[item.get("role")] = roles.get(item.get("role"), 0) + 1
    print(f"端口 {port}｜条目 {len(items)}｜role {roles}")
    print(f"facets.role = {catalog['facets'].get('role')}")

    html = urllib.request.urlopen(base + "/index.html", timeout=15).read().decode("utf-8")
    # searchHist / histClear 必须存在；fRole（"入口范围"过滤）已按反馈回退，
    # viewer（软件内打开窗口）也已在改成"一律用系统浏览器打开"后移除，都不应再出现
    for marker, want in (("searchHist", True), ("histClear", True), ("fRole", False),
                         ("offlineBar", True), ("emptyBoot", True), ("viewer", False),
                         ("profileModes", False)):
        got = marker in html
        print(f"  前端包含 {marker}: {got}（期望 {want}）{'✔' if got == want else '✘'}")

    ping = json.loads(urllib.request.urlopen(base + "/api/ping", timeout=5).read().decode("utf-8"))
    print(f"/api/ping -> {ping}")

    q = "宿舍报修"
    print(f"/api/history 记录「{q}」-> {post(base, '/api/history', {'query': q})['history']}")
    print(f"/api/history 清空 -> {post(base, '/api/history', {'clear': True})['history']}")
    user = json.loads(urllib.request.urlopen(base + "/api/userdata", timeout=15).read().decode("utf-8"))
    print(f"userdata: favorites={user.get('favorites')} recent={user.get('recent')} history={user.get('history')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
