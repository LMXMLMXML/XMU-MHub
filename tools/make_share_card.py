# -*- coding: utf-8 -*-
"""生成分享卡片图（微信/QQ 群里发链接时显示的那张图）。

600×480，藏青底 + 门户 LOGO + 标题副标题，输出 web/assets/logo/share-card.png。
之所以要专门做一张：微信读 og:image 时对尺寸和比例敏感，太小的图不显示；
直接拿 512 的方形图标凑数会显示成一个小方块。

用法：python tools/make_share_card.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "web" / "assets" / "logo" / "logo-256.png"
OUT = ROOT / "web" / "assets" / "logo" / "share-card.png"

W, H = 600, 480
BRAND = (13, 47, 110)
ACCENT = (12, 129, 189)
GREEN = (79, 158, 63)


def main() -> int:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("需要 Pillow：python -m pip install --target .buildtools pillow，再带上 PYTHONPATH 运行")
        return 1

    img = Image.new("RGB", (W, H), BRAND)
    draw = ImageDraw.Draw(img)

    # 背景：左上到右下的轻微渐变 + 右下角一抹 OH 绿
    for y in range(H):
        for_x = y / H
        draw.line([(0, y), (W, y)],
                  fill=(int(BRAND[0] + 10 * for_x), int(BRAND[1] + 18 * for_x), int(BRAND[2] + 26 * for_x)))
    draw.ellipse([W - 210, H - 150, W + 60, H + 120], fill=(*GREEN, ))
    draw.ellipse([-90, -120, 170, 140], fill=(*ACCENT, ))

    # LOGO（白底圆角卡片，避免深色底上图标看不清）
    if LOGO.exists():
        logo = Image.open(LOGO).convert("RGBA")
        logo.thumbnail((140, 140), Image.LANCZOS)
        card = Image.new("RGBA", (logo.width + 36, logo.height + 36), (255, 255, 255, 255))
        card.paste(logo, (18, 18), logo)
        mask = Image.new("L", card.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, card.width - 1, card.height - 1], 24, fill=255)
        img.paste(card, (44, 96), mask)

    def font(size: int):
        for name in ("msyhbd.ttc", "msyh.ttc", "simhei.ttf", "simsun.ttc"):
            try:
                return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
            except Exception:  # noqa: BLE001
                continue
        return ImageFont.load_default()

    # 文字从 LOGO 卡片右侧开始（卡片 44 + 176 = 220），留 26px 间隙
    left = 246
    draw.text((left, 132), "厦大统一门户", font=font(44), fill=(255, 255, 255))
    draw.text((left + 2, 196), "全校入口 一次找齐", font=font(25), fill=(178, 208, 240))
    draw.text((left + 2, 246), "320 条网站 · 系统 · 小程序", font=font(20), fill=(150, 186, 226))
    draw.text((left + 2, 276), "按校区 / 对象 / 用途分类", font=font(20), fill=(150, 186, 226))
    draw.text((44, H - 58), "说一句「宿舍水管漏了」就知道该去哪办", font=font(21), fill=(226, 238, 252))

    img.save(OUT, "PNG", optimize=True)
    print(f"已生成 {OUT}（{OUT.stat().st_size // 1024} KB，{W}×{H}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
