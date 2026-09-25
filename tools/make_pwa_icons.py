# -*- coding: utf-8 -*-
"""从 logo-512.png 生成 PWA 需要的其它尺寸（192 是 Chrome 判定"可安装"的硬要求）。

Chrome 的安装条件里写明：manifest 的 icons 至少要包含 192px 和 512px 两个尺寸。
我们原来只有 128/256/512，所以浏览器一直不给安装提示。

用法：python tools/make_pwa_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "web" / "assets" / "logo" / "logo-512.png"
SIZES = (192, 384)


def main() -> int:
    if not SRC.exists():
        print(f"缺少 {SRC}")
        return 1
    try:
        from PIL import Image
    except ImportError:
        print("需要 Pillow：python -m pip install --target .buildtools pillow，再带上 PYTHONPATH 运行")
        return 1

    src = Image.open(SRC).convert("RGBA")
    for size in SIZES:
        out = SRC.parent / f"logo-{size}.png"
        src.resize((size, size), Image.LANCZOS).save(out, "PNG", optimize=True)
        print(f"已生成 {out.name}（{out.stat().st_size // 1024} KB，{size}×{size}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
