# -*- coding: utf-8 -*-
"""生成「厦大统一门户」独立 LOGO（纯图形、无任何文字）。

语义（每笔都有出处，详见 web/assets/logo/DESIGN.md）：
  · 深蓝圆角方  厦门大学校徽藏青 #0d2f6e（实测占校徽像素 80.5%）
  · 白色门洞    嘉庚建筑飞檐 + 敞开的大门 = 「统一门户」本身
  · 青色浪纹    临海厦大 / 信息流（信息学院强调蓝 #0c81bd）
  · 绿色开放环  OpenHarmony 的几何开放环语言（#4f9e3f→#75c754），底部留口 = 开放生态
  · 三路汇入    散落的网站/小程序/公众号汇入一个入口；左右上对称三路 = 校区/对象/用途三个维度
  · 圆点        三路汇聚的起点，也是 OH 的几何点语言

产出（web/assets/logo/）：
  logo-portal.svg / -light.svg / -mark.svg / -mono.svg
  logo-512.png / -256 / -128 / -64 / -32 / -512-light.png / -256-mark.png
  favicon.ico / logo-preview.png
用法：PYTHONPATH=.buildtools python tools/make_logo.py
"""
from __future__ import annotations

import math
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "assets" / "logo"

S = 512
SS = 4
NAVY_DARK, NAVY, NAVY_LIGHT = "#082457", "#0d2f6e", "#1b4494"
ACCENT, ACCENT_DEEP = "#4aa8d8", "#0c81bd"
OH_GREEN, OH_GREEN_L = "#4f9e3f", "#75c754"
WHITE, SOFT = "#ffffff", "#e8f1fc"

# ---- 几何常量（512 栅格；pt(): 0°=右，90°=下）----
RING_C = (256.0, 258.0)
RING_R = 180.0
RING_W = 23.0
RING_GAP = 74.0                 # 底部开口（门从这里立出去）
RING_START = 90 + RING_GAP / 2
RING_END = 90 - RING_GAP / 2 + 360

# 环上的点：散落的网站/小程序/公众号，围绕门户排布（OH 的几何点语言）
RING_DOTS = [-166.0, -136.0, -106.0, -76.0, -46.0, -16.0]
RING_DOT_R = 13.0

GATE_CX = 256.0
GATE_BASE = 448.0               # 门穿过环的开口（门户"破环而入"）
GATE_TOP = 258.0                # 拱顶圆心高度
GATE_HALF_OUT = 80.0
GATE_HALF_IN = 56.0
GATE_ARCH_IN_TOP = 306.0        # 门洞拱顶圆心

ROOF_Y = 232.0                  # 屋脊中心线
ROOF_HALF = 104.0
ROOF_THICK = 28.0
ROOF_LIFT = 20.0                # 两端上翘（燕尾脊）

WAVE_Y = 376.0
WAVE_AMP = 14.0
WAVE_W = 16.0


def hex_rgb(v: str) -> tuple[int, int, int]:
    v = v.lstrip("#")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def mix(c1: str, c2: str, t: float) -> tuple[int, int, int]:
    a, b = hex_rgb(c1), hex_rgb(c2)
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def pt(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    rad = math.radians(deg)
    return (cx + r * math.cos(rad), cy + r * math.sin(rad))


def arch_points(cx: float, base: float, arch_cy: float, half: float, steps: int = 56) -> list[tuple[float, float]]:
    """半圆拱 + 两条竖直边（顺时针：左底→拱顶→右底）。"""
    pts = [(cx - half, base)]
    pts += [pt(cx, arch_cy, half, 180 + 180 * i / steps) for i in range(steps + 1)]
    pts.append((cx + half, base))
    return pts


def roof_points(steps: int = 96) -> list[tuple[float, float]]:
    """嘉庚燕尾脊：中间平缓、两端上翘并收细的屋脊。"""
    def ridge(t: float) -> tuple[float, float]:
        u = (t - 0.5) * 2
        x = GATE_CX + ROOF_HALF * u
        return x, ROOF_Y - ROOF_LIFT * abs(u) ** 3.2

    def thick(u: float) -> float:
        return ROOF_THICK * (1.0 - 0.34 * abs(u) ** 2.4)

    top = []
    for i in range(steps + 1):
        t = i / steps
        x, y = ridge(t)
        top.append((x, y))
    bottom = []
    for i in range(steps, -1, -1):
        t = i / steps
        u = (t - 0.5) * 2
        x, y = ridge(t)
        bottom.append((x, y + thick(u)))
    return top + bottom


def wave_points() -> list[tuple[float, float]]:
    pts = []
    x = GATE_CX - GATE_HALF_IN + 2
    while x <= GATE_CX + GATE_HALF_IN - 2:
        pts.append((x, WAVE_Y + WAVE_AMP * math.sin((x - GATE_CX) / 13.0)))
        x += 3
    return pts


def flow_curve(deg: float, r_scale: float) -> list[tuple[float, float]]:
    """（保留：把环上的点连到屋脊，用于"多路汇入"的细线版本）"""
    x0, y0 = pt(RING_C[0], RING_C[1], RING_R * r_scale, deg)
    ex, ey = GATE_CX, ROOF_Y - 2.0
    cxp = (x0 + ex) / 2 + (18.0 if deg < -90 else -18.0 if deg > -90 else 0.0)
    cyp = min(y0, ey) - 30.0
    pts = []
    for i in range(26):
        t = i / 25
        bx = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cxp + t * t * ex
        by = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cyp + t * t * ey
        pts.append((bx, by))
    return pts


def fmt(pts: list[tuple[float, float]], close: bool = True) -> str:
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return d + " Z" if close else d


# ---------------------------------------------------------------- SVG

def build_svg(*, background: str | None = "navy", detail: bool = True, mono: str | None = None) -> str:
    def col(c: str) -> str:
        return mono or c

    defs: list[str] = []
    bg = ""
    if background == "navy":
        defs += [
            '<linearGradient id="bg" x1="0" y1="0" x2="0.35" y2="1">'
            f'<stop offset="0" stop-color="{NAVY_LIGHT}"/><stop offset="0.45" stop-color="{NAVY}"/>'
            f'<stop offset="1" stop-color="{NAVY_DARK}"/></linearGradient>',
            '<radialGradient id="glow" cx="0.3" cy="0.2" r="0.72">'
            '<stop offset="0" stop-color="#5b9bff" stop-opacity="0.30"/>'
            '<stop offset="1" stop-color="#5b9bff" stop-opacity="0"/></radialGradient>',
        ]
        bg = (f'<rect width="{S}" height="{S}" rx="120" fill="url(#bg)"/>'
              f'<rect width="{S}" height="{S}" rx="120" fill="url(#glow)"/>')
    elif background == "light":
        defs.append('<linearGradient id="bg" x1="0" y1="0" x2="0.4" y2="1">'
                    f'<stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="{SOFT}"/>'
                    '</linearGradient>')
        bg = (f'<rect width="{S}" height="{S}" rx="120" fill="url(#bg)"/>'
              f'<rect x="1.2" y="1.2" width="{S - 2.4}" height="{S - 2.4}" rx="119" fill="none" '
              f'stroke="{NAVY}" stroke-opacity="0.12" stroke-width="2.4"/>')
    defs.append('<linearGradient id="ring" x1="0.1" y1="0" x2="0.9" y2="1">'
                f'<stop offset="0" stop-color="{col(OH_GREEN_L)}"/>'
                f'<stop offset="1" stop-color="{col(OH_GREEN)}"/></linearGradient>')

    gate = col(WHITE if background == "navy" else NAVY)
    accent = col(ACCENT if background == "navy" else ACCENT_DEEP)

    x1, y1 = pt(*RING_C, RING_R, RING_START)
    x2, y2 = pt(*RING_C, RING_R, RING_END)
    ring = (f"M {x1:.1f},{y1:.1f} A {RING_R},{RING_R} 0 1 1 {x2:.1f},{y2:.1f}")

    outer = fmt(arch_points(GATE_CX, GATE_BASE, GATE_TOP, GATE_HALF_OUT))
    inner = fmt(arch_points(GATE_CX, GATE_BASE + 2, GATE_ARCH_IN_TOP, GATE_HALF_IN))

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" width="{S}" height="{S}" '
             f'role="img" aria-label="厦大统一门户：多路汇入一个门户">',
             "<defs>" + "".join(defs) + "</defs>", bg,
             f'<path d="{ring}" fill="none" stroke="url(#ring)" stroke-width="{RING_W}" '
             f'stroke-linecap="round"/>']

    if detail:
        # 环上的点 = 散落的网站/小程序/公众号
        for deg in RING_DOTS:
            cx, cy = pt(RING_C[0], RING_C[1], RING_R, deg)
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{RING_DOT_R}" fill="{accent}"/>')

    # 门（even-odd 挖出门洞）+ 飞檐
    parts.append(f'<path d="{outer} {inner}" fill="{gate}" fill-rule="evenodd"/>')
    parts.append(f'<path d="{fmt(roof_points())}" fill="{gate}"/>')
    if detail:
        parts.append(f'<path d="{fmt(wave_points(), close=False)}" fill="none" stroke="{accent}" '
                     f'stroke-width="{WAVE_W}" stroke-linecap="round"/>')
    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------- PNG（Pillow）

def vgrad(size: int, c1: str, c2: str) -> Image.Image:
    strip = Image.new("RGB", (1, size))
    for y in range(size):
        strip.putpixel((0, y), mix(c1, c2, y / max(1, size - 1)))
    return strip.resize((size, size), Image.BILINEAR)


def rounded_mask(size: int, radius: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def arc_gradient(layer: Image.Image, cx: float, cy: float, r: float, w: float,
                 a0: float, a1: float, c0: str, c1: str, steps: int = 260) -> None:
    draw = ImageDraw.Draw(layer)
    for i in range(steps):
        t0 = a0 + (a1 - a0) * i / steps
        t1 = t0 + (a1 - a0) / steps + 0.7
        draw.arc([cx - r, cy - r, cx + r, cy + r], t0, t1, fill=mix(c0, c1, i / steps), width=int(w))
    for deg, tt in ((a0, 0.0), (a1, 1.0)):
        x, y = pt(cx, cy, r, deg)
        draw.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=mix(c0, c1, tt))


def scale(pts: list[tuple[float, float]], k: float) -> list[tuple[float, float]]:
    return [(x * k, y * k) for x, y in pts]


def render_png(size: int, *, background: str | None = "navy", detail: bool = True,
               mono: str | None = None) -> Image.Image:
    global ROOF_LIFT, ROOF_THICK, RING_W
    saved = (ROOF_LIFT, ROOF_THICK, RING_W)
    if not detail:
        # 小尺寸：环加粗、屋脊上翘减弱，缩到 16–32px 才不会糊成一团
        ROOF_LIFT, ROOF_THICK, RING_W = 10.0, 26.0, 28.0
    try:
        return _render_png(size, background=background, detail=detail, mono=mono)
    finally:
        ROOF_LIFT, ROOF_THICK, RING_W = saved


def _render_png(size: int, *, background: str | None, detail: bool, mono: str | None) -> Image.Image:
    big = size * SS
    k = big / S
    canvas = Image.new("RGBA", (big, big), (0, 0, 0, 0))

    if background == "navy":
        base = vgrad(big, NAVY_LIGHT, NAVY_DARK).convert("RGBA")
        base.putalpha(rounded_mask(big, int(120 * k)))
        canvas = Image.alpha_composite(canvas, base)
        glow = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([-big * 0.3, -big * 0.34, big * 0.9, big * 0.78], fill=(91, 155, 255, 88))
        glow = glow.filter(ImageFilter.GaussianBlur(big * 0.13))
        glow.putalpha(Image.composite(glow.getchannel("A"), Image.new("L", (big, big), 0),
                                      rounded_mask(big, int(120 * k))))
        canvas = Image.alpha_composite(canvas, glow)
    elif background == "light":
        base = vgrad(big, "#ffffff", SOFT).convert("RGBA")
        base.putalpha(rounded_mask(big, int(120 * k)))
        canvas = Image.alpha_composite(canvas, base)

    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    gate = mono or (WHITE if background == "navy" else NAVY)
    accent = mono or (ACCENT if background == "navy" else ACCENT_DEEP)

    # 绿色开放环
    arc_gradient(layer, RING_C[0] * k, RING_C[1] * k, RING_R * k, RING_W * k,
                 RING_START, RING_END, mono or OH_GREEN_L, mono or OH_GREEN)

    if detail:
        for deg in RING_DOTS:
            x, y = pt(RING_C[0] * k, RING_C[1] * k, RING_R * k, deg)
            draw.ellipse([x - RING_DOT_R * k, y - RING_DOT_R * k, x + RING_DOT_R * k, y + RING_DOT_R * k],
                         fill=accent)

    # 门（先画实心，再把门洞挖掉）
    draw.polygon(scale(arch_points(GATE_CX, GATE_BASE, GATE_TOP, GATE_HALF_OUT), k), fill=gate)
    draw.polygon(scale(roof_points(), k), fill=gate)
    hole = Image.new("L", (big, big), 0)
    ImageDraw.Draw(hole).polygon(scale(arch_points(GATE_CX, GATE_BASE + 2, GATE_ARCH_IN_TOP, GATE_HALF_IN), k), fill=255)
    layer.paste((0, 0, 0, 0), mask=hole)

    if detail:
        wave = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        ImageDraw.Draw(wave).line(scale(wave_points(), k), fill=accent,
                                  width=int(WAVE_W * k), joint="curve")
        wave.putalpha(Image.composite(wave.getchannel("A"), Image.new("L", (big, big), 0),
                                      hole.filter(ImageFilter.MaxFilter(3))))
        layer = Image.alpha_composite(layer, wave)

    canvas = Image.alpha_composite(canvas, layer)
    return canvas.resize((size, size), Image.LANCZOS)


def write_ico(path: Path, specs: list[tuple[int, bool]]) -> None:
    """手写 ICO 容器：每个尺寸用各自的图形（小尺寸用简化版），而不是把大图缩小。

    规格：(尺寸, 是否完整版)。Windows 允许 ICO 里放 PNG（Vista+）。
    """
    images = []
    for size, detail in specs:
        img = render_png(size, detail=detail)
        buf = __import__("io").BytesIO()
        img.save(buf, format="PNG")
        images.append((size, buf.getvalue()))

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    path.write_bytes(header + entries + blobs)


def preview() -> None:
    """对照图：深底尺寸阶梯 + 浅底 / 透明标 / 单色标（仅文档用，不参与 LOGO 本身）。"""
    W, H = 1240, 560
    sheet = Image.new("RGB", (W, H), (243, 246, 252))
    draw = ImageDraw.Draw(sheet)

    # 第一行：深底尺寸阶梯
    y = 60
    x = 56
    for size in (256, 128, 64, 32):
        sheet.paste(render_png(size, detail=size > 32), (x, y + (256 - size) // 2),
                    render_png(size, detail=size > 32))
        x += size + 46

    # 第二行：浅底 / 透明（垫浅色卡片）/ 单色
    y = 372
    chips = [
        (128, render_png(128, background="light"), (255, 255, 255)),
        (128, render_png(128, background=None), (255, 255, 255)),
        (128, render_png(128, background=None, mono=NAVY), (255, 255, 255)),
        (128, render_png(128, background=None, mono=WHITE), (13, 47, 110)),
    ]
    x = 56
    for size, img, chip in chips:
        draw.rounded_rectangle([x - 6, y - 6, x + size + 6, y + size + 6], radius=int(size * 0.24),
                               fill=chip, outline=(214, 222, 236))
        sheet.paste(img, (x, y), img)
        x += size + 46

    sheet.save(OUT / "logo-preview.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    svgs = {
        "logo-portal.svg": build_svg(background="navy", detail=True),
        "logo-portal-light.svg": build_svg(background="light", detail=True),
        "logo-portal-mark.svg": build_svg(background=None, detail=True),
        "logo-portal-mono.svg": build_svg(background=None, detail=True, mono=WHITE),
    }
    for name, text in svgs.items():
        (OUT / name).write_text(text, encoding="utf-8")

    for size in (512, 256, 128, 64):
        render_png(size).save(OUT / f"logo-{size}.png")
    render_png(32, detail=False).save(OUT / "logo-32.png")
    render_png(512, background="light").save(OUT / "logo-512-light.png")
    render_png(256, background=None).save(OUT / "logo-256-mark.png")
    render_png(256, detail=False).save(OUT / "favicon.ico",
                                      sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    # Windows 应用程序图标：小尺寸用简化图形，大尺寸用完整图形
    write_ico(OUT / "app.ico", [(16, False), (24, False), (32, False),
                                (48, True), (64, True), (128, True), (256, True)])
    preview()

    for path in sorted(OUT.iterdir()):
        print(f"{path.name:28s} {path.stat().st_size:>8,d} B")


if __name__ == "__main__":
    main()
