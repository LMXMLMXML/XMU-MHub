# -*- coding: utf-8 -*-
"""打包"手机版静态站"：把 web/ 与目录数据拼成一个可以直接托管的文件夹。

产物：dist-mobile/
    index.html  app.js  styles.css  sw.js  manifest.json
    portal.json          ← 从 data/portal.json 复制过来（前端读不到后端时就读它）
    assets/…             ← 校徽、院徽、LOGO、字体等

这一份东西不需要 Python、不需要安装，丢到任意静态托管（校内服务器 / GitHub Pages /
对象存储 / nginx）就能用；手机浏览器打开后可以"添加到主屏幕"，装了就是 App。

用法：
    python tools/build_mobile.py
    python tools/preview_mobile.py        # 本机起个静态服务，用手机连同一 WiFi 预览
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DATA = ROOT / "data" / "portal.json"
OUT = ROOT / "dist-mobile"

# 桌面版才用的东西，手机版不需要
SKIP = {"logo-preview.png", "DESIGN.md"}

# 各家静态托管认的配置文件（Netlify / Cloudflare Pages 都读 _headers）
HEADERS = """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: SAMEORIGIN

/portal.json
  Cache-Control: no-cache

/sw.js
  Cache-Control: no-cache

/index.html
  Cache-Control: no-cache

/assets/*
  Cache-Control: public, max-age=604800
"""

ROBOTS = """User-agent: *
Allow: /

# 学生作品，非厦门大学官方产品
"""


def write_extras(out: Path) -> list[str]:
    """写上托管平台要用的零碎文件，省得每次部署都手动加。"""
    (out / "_headers").write_text(HEADERS, encoding="utf-8")
    (out / "robots.txt").write_text(ROBOTS, encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")   # GitHub Pages 不要走 Jekyll
    return ["_headers", "robots.txt", ".nojekyll"]


def copy_tree(src: Path, dst: Path) -> int:
    count = 0
    for path in src.rglob("*"):
        if path.is_dir() or path.name in SKIP:
            continue
        target = dst / path.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        count += 1
    return count


def main() -> int:
    if not DATA.exists():
        print(f"缺少 {DATA}，请先运行：python tools/build_data.py")
        return 1

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    copied = copy_tree(WEB, OUT)
    shutil.copy2(DATA, OUT / "portal.json")
    extras = write_extras(OUT)

    catalog = json.loads(DATA.read_text(encoding="utf-8"))
    items = catalog.get("items", [])
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())

    print(f"已生成 {OUT}")
    print(f"  文件 {copied + 1 + len(extras)} 个｜合计 {size / 1024:.0f} KB｜收录 {len(items)} 条")
    print(f"  目录数据 portal.json：{(OUT / 'portal.json').stat().st_size / 1024:.0f} KB")
    print(f"  托管用的小文件：{'、'.join(extras)}")
    print()
    print("下一步（三选一，都是把这个目录整个传上去）：")
    print("  本地预览   python tools/preview_mobile.py            # 手机连同一 WiFi 看效果")
    print("  公网部署   见 DEPLOY.md（Cloudflare Pages / Netlify / GitHub Pages 三条路线）")
    print("  部署验收   python tools/deploy_check.py https://你的网址/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
