"""下载品牌素材（校徽 / 信息学院院徽 / OpenHarmony 标识）并报告基本信息。"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from pathlib import Path

# --- 仓库根目录，随 clone 位置自适应（原来这里写死了 D:\AI\xmu_hub）---
ROOT = Path(__file__).resolve().parent.parent


OUT = ROOT / "web" / "assets"
OUT.mkdir(parents=True, exist_ok=True)
REPORT = ROOT / "data" / "_assets.txt"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def fetch(url: str, referer: str | None = None, timeout: int = 45) -> tuple[int, bytes, str]:
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        return exc.code, b"", exc.headers.get("Content-Type", "") if exc.headers else ""
    except Exception as exc:  # noqa: BLE001
        return -1, str(exc).encode(), ""


lines: list[str] = []

# 1) 厦门大学校徽（学校标识页）
emblem = ("https://www.xmu.edu.cn/virtual_attach_file.vsb?afc=enR9yZUlnRLmU4nhRG4LlU8M8nfoln3Rnln7UzVk"
          "UzVkLmC0gihFp2hmCIa0LYyinSyioSysMR74UlC8UznRMl-PMRlaUzC8U4GiMzM2MzQFL8UDnNWVMRVFolLDM1b/v2"
          "veo4Oe_2iigDTJQty0LzGaokyPLRCigtA8pUBcc&tid=1008&nid=1065&e=.jpg")
status, data, ctype = fetch(emblem, referer="https://www.xmu.edu.cn/sdgl/xxbs.htm")
lines.append(f"[校徽] HTTP {status} {ctype} {len(data)} bytes")
if status == 200 and data:
    (OUT / "xmu-emblem.jpg").write_bytes(data)

# 2) 信息学院院徽（学院院徽页）
informatics = ("https://www.xmu.edu.cn/virtual_attach_file.vsb?afc=5nRGC4MNC8n7L8MQml8UNV7LRlZL49qanRG4"
               "nm94Mm-8nRL0gihFp2hmCIa0nSy8USyaMYyiLlMfMNQVMlLaMl-ZL8WfLz9aMm7aMRL8M8VFL7-bn7UaLRTF"
               "nR-4UmCJqjfjo4OeosAx6ShXptQ0gY84gY84gtA8pUpcc&e=.jpg")
status, data, ctype = fetch(informatics, referer="https://www.xmu.edu.cn/sdgl/xyyh1.htm")
lines.append(f"[信息学院院徽] HTTP {status} {ctype} {len(data)} bytes")
if status == 200 and data:
    (OUT / "informatics-emblem.jpg").write_bytes(data)

# 3) 信息学院站点自带 logo
for name, url in (
    ("informatics-site-logo", "https://informatics.xmu.edu.cn/images/logo.png"),
    ("xmu-site-logo", "https://www.xmu.edu.cn/images/logo.png"),
    ("xmu-site-logo2", "https://www.xmu.edu.cn/images/logo2.png"),
):
    status, data, ctype = fetch(url, referer="https://informatics.xmu.edu.cn/")
    lines.append(f"[{name}] HTTP {status} {ctype} {len(data)} bytes")
    if status == 200 and data:
        suffix = ".png" if "png" in ctype else ".jpg"
        (OUT / f"{name}{suffix}").write_bytes(data)

# 4) OpenHarmony 官方标识
status, html, _ = fetch("https://www.openharmony.cn/")
lines.append(f"\n[OpenHarmony 首页] HTTP {status}, {len(html)} bytes")
if status == 200:
    text = html.decode("utf-8", "ignore")
    cands = set(re.findall(r'(?:src|href)="([^"]+\.(?:svg|png|jpg|ico))"', text))
    picked = [c for c in cands if any(k in c.lower() for k in ("logo", "icon", "favicon", "brand"))]
    lines.append("  候选图片: " + (", ".join(sorted(picked)[:12]) or "（无）"))
    for i, rel in enumerate(sorted(picked)[:6]):
        url = rel if rel.startswith("http") else "https://www.openharmony.cn/" + rel.lstrip("/")
        st, blob, ct = fetch(url)
        lines.append(f"  下载 {rel}: HTTP {st} {ct} {len(blob)} bytes")
        if st == 200 and blob:
            suffix = Path(rel).suffix or ".png"
            (OUT / f"openharmony-{i}{suffix}").write_bytes(blob)

lines.append("\n=== 已保存文件 ===")
for path in sorted(OUT.iterdir()):
    lines.append(f"  {path.name}  {path.stat().st_size} bytes")

REPORT.write_text("\n".join(lines), encoding="utf-8")
print("written")
