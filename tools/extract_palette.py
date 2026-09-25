"""从品牌素材中提取主色，作为前端配色依据。"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"D:\AI\.pylibs")
from PIL import Image  # noqa: E402

ASSETS = Path(r"D:\AI\xmu_hub\web\assets")
OUT = Path(r"D:\AI\xmu_hub\data\_palette.txt")
lines: list[str] = []


def quantize(img: Image.Image, colors: int = 8) -> list[tuple[str, float]]:
    small = img.convert("RGB").resize((120, 120))
    pal = small.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
    counts = Counter(pal.getdata())
    total = sum(counts.values())
    result = []
    for rgb, n in counts.most_common(colors):
        result.append(("#%02x%02x%02x" % rgb, round(n / total * 100, 1)))
    return result


def is_meaningful(hex_color: str) -> bool:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    if r > 238 and g > 238 and b > 238:   # 近白（多为透明底）
        return False
    if r < 18 and g < 18 and b < 18:      # 近黑
        return False
    return True


for path in sorted(ASSETS.iterdir()):
    try:
        img = Image.open(path)
    except Exception as exc:  # noqa: BLE001
        lines.append(f"[{path.name}] 打不开：{exc}")
        continue
    lines.append(f"[{path.name}] {img.size[0]}x{img.size[1]} {img.mode} {path.stat().st_size} bytes")
    for hex_color, pct in quantize(img):
        flag = "  " if is_meaningful(hex_color) else "  (白/黑底)"
        lines.append(f"    {hex_color}  {pct:>5}%{flag}")
    # 若是图标，导出 PNG 便于预览
    if path.suffix.lower() == ".ico":
        png = path.with_suffix(".png")
        img.convert("RGBA").save(png)
        lines.append(f"    → 已导出预览：{png.name}")
    lines.append("")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("written")
