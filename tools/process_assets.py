"""把官方 LOGO 处理成前端可直接使用的素材。

处理内容：
  1. 去掉白底（转为透明 PNG）
  2. 裁掉四周空白、统一缩放
  3. 额外生成"单色白"版本，供深色主题使用
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(_WORKSPACE / ".pylibs"))
from PIL import Image, ImageOps  # noqa: E402

# --- 仓库根目录，随 clone 位置自适应（原来这里写死了 D:\AI\xmu_hub）---
ROOT = Path(__file__).resolve().parent.parent

# 工作区根（仓库外的东西：本地依赖库等）
_WORKSPACE = ROOT.parent


ASSETS = ROOT / "web" / "assets"
OUT = ROOT / "data" / "_assets_processed.txt"
lines: list[str] = []


def strip_white(img: Image.Image, threshold: int = 238) -> Image.Image:
    """白底转透明。"""
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r >= threshold and g >= threshold and b >= threshold:
                px[x, y] = (r, g, b, 0)
            elif r > threshold - 22 and g > threshold - 22 and b > threshold - 22:
                # 边缘半透明，避免锯齿
                px[x, y] = (r, g, b, int(a * 0.35))
    return img


def crop_content(img: Image.Image, pad: int = 6) -> Image.Image:
    bbox = img.getbbox()
    if not bbox:
        return img
    left, top, right, bottom = bbox
    return img.crop((
        max(0, left - pad), max(0, top - pad),
        min(img.width, right + pad), min(img.height, bottom + pad),
    ))


def mono_white(img: Image.Image) -> Image.Image:
    """用亮度做遮罩，生成纯白单色版（深色主题用）。"""
    gray = ImageOps.grayscale(img.convert("RGB"))
    alpha = ImageOps.invert(gray)
    white = Image.new("RGBA", img.size, (255, 255, 255, 255))
    white.putalpha(alpha)
    return white


def process(src_name: str, out_name: str, size: int) -> None:
    src = ASSETS / src_name
    if not src.exists():
        lines.append(f"[{src_name}] 不存在，跳过")
        return
    img = Image.open(src)
    clean = crop_content(strip_white(img))
    # 等比缩放到目标高度
    ratio = size / max(clean.size)
    new_size = (max(1, round(clean.width * ratio)), max(1, round(clean.height * ratio)))
    clean = clean.resize(new_size, Image.LANCZOS)
    clean.save(ASSETS / f"{out_name}.png")
    mono = mono_white(clean)
    mono.save(ASSETS / f"{out_name}-white.png")
    lines.append(f"[{src_name}] {img.size} → {out_name}.png {clean.size} "
                 f"({(ASSETS / f'{out_name}.png').stat().st_size} bytes) + 白色版")


process("xmu-emblem.jpg", "xmu-emblem", 160)
process("informatics-emblem.jpg", "informatics-emblem", 200)

# OpenHarmony favicon → PNG（作为 OH 配色来源留档）
ico = ASSETS / "openharmony-0.ico"
if ico.exists():
    Image.open(ico).convert("RGBA").resize((64, 64), Image.LANCZOS).save(ASSETS / "openharmony.png")
    lines.append("[openharmony-0.ico] → openharmony.png 64x64")

lines.append("\n=== assets 目录 ===")
for path in sorted(ASSETS.iterdir()):
    lines.append(f"  {path.name}  {path.stat().st_size} bytes")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("written")
