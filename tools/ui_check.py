"""前端与接口静态校验（无浏览器环境下的替代验证）。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

# --- 仓库根目录，随 clone 位置自适应（原来这里写死了 D:\AI\xmu_hub）---
ROOT = Path(__file__).resolve().parent.parent


PORT_FILE = ROOT / "data" / "_runtime_port.txt"


def _runtime_port() -> int:
    """读取程序实际监听端口，避免端口被旧实例占用时测试打到旧数据。"""
    try:
        return int(PORT_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return 8765


BASE = "http://127.0.0.1:" + str(_runtime_port())
WEB = ROOT / "web"
OUT = ROOT / "data" / "_ui_check.txt"
lines: list[str] = []

# 1. 静态资源
for name in ("index.html", "styles.css", "app.js"):
    try:
        with urllib.request.urlopen(f"{BASE}/{name}", timeout=15) as resp:
            body = resp.read().decode("utf-8")
        lines.append(f"[static] {name}: HTTP {resp.status}, {len(body)} chars")
        if name == "index.html":
            for anchor in ("fCampus", "fAudience", "fPurpose", "fKind", "list", "aiPanel", "app.js"):
                lines.append(f"    contains {anchor}: {anchor in body}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"[static] {name}: ERROR {exc}")

# 2. 前端引用的 DOM id 是否都存在于 HTML
html = (WEB / "index.html").read_text(encoding="utf-8")
js = (WEB / "app.js").read_text(encoding="utf-8")
import re


ids_used = set(re.findall(r"""\$\('#([A-Za-z0-9_-]+)'\)""", js))
ids_defined = set(re.findall(r'id="([A-Za-z0-9_-]+)"', html))
# 这些 id 是 JS 用模板字符串动态生成后再查询的（本机模型区块、装到主屏的自检行），
# 静态 HTML 里本来就没有，属于正常情况
DYNAMIC_IDS = {"akLocalPick", "akLocalUse", "akInstall", "akInstallCustom", "akServe",
               "akSetupUrl", "installWhy"}
missing = sorted(ids_used - ids_defined - DYNAMIC_IDS)
lines.append(f"\n[dom] js 引用 {len(ids_used)} 个 id，html 定义 {len(ids_defined)} 个"
             f"（另有 {len(DYNAMIC_IDS)} 个由 JS 动态生成）")
lines.append(f"[dom] 缺失的 id: {missing or '无'}")

# 2.5 样式表体检（防止改版后变量漏定义 / 括号不配对 / 关键回归规则丢失）
css = (WEB / "styles.css").read_text(encoding="utf-8")
lines.append(f"\n[css] 长度 {len(css)} 字符，花括号 {css.count('{')}/{css.count('}')} "
             f"（{'配对' if css.count('{') == css.count('}') else '不配对！'}）")
for token in ("--brand", "--brand-mid", "--accent", "--accent-lit", "--oh-green",
              "--pc", "--mobile", "--both", "--offline", "--mono", "--border"):
    lines.append(f"   变量 {token}: {'已定义' if re.search(re.escape(token) + r'\s*:', css) else '缺失！'}")
for rule in (r"\[hidden\]\s*\{[^}]*display:\s*none", r"\.badge\.plat\.mobile",
             r"\.badge\.plat\.pc", r"\.badge\.plat\.both", r"\.card::before",
             r"\.stats \.bar", r"\.card\.plat-mobile", r"\.palette-panel",
             r"\.topbar::after", r'\[data-theme="dark"\]', r"assets/xmu-emblem"):
    lines.append(f"   规则 {rule}: {'存在' if re.search(rule, css) else '缺失！'}")
unused_braces = re.findall(r"purple", css)
lines.append(f"   残留占位符(purple): {len(unused_braces)} 处")

# 2.6 弹层防复发：遮罩选择器必须用 ID，且 JS 不能生成同名 class
#（曾经因为抽屉内容里套了 <div class="drawer"> 而被当成全屏遮罩，盖住关闭按钮）
lines.append("\n[overlay] 弹层选择器与类名冲突检查")
for ident in ("drawer", "palette", "aiPanel"):
    scoped = re.search(rf"#{ident} \{{[^}}]*position:\s*fixed", css) is not None
    lines.append(f"   #{ident} 用 ID 限定为 fixed 遮罩: {'是' if scoped else '否！'}")
for cls in ("drawer", "palette", "aipanel"):
    hits = re.findall(rf'class="{cls}[" ]', js)
    lines.append(f"   app.js 生成 class=\"{cls}\" 的次数: {len(hits)}（应为 0）")
bare = re.findall(rf"^\.{'(?:drawer|palette|aipanel)'}\s*\{{", css, flags=re.M)
lines.append(f"   裸类选择器 .drawer/.palette/.aipanel: {len(bare)} 个（应为 0）")

# 3. 接口边界
def call(path: str, payload: dict | None = None):
    if payload is None:
        req = urllib.request.Request(BASE + path)
    else:
        req = urllib.request.Request(
            BASE + path,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "ignore")[:120]

lines.append("")
lines.append(f"[api] 空问题 -> {call('/api/ask', {'question': ''})}")
lines.append(f"[api] 目录外网址打开 -> {call('/api/open', {'url': 'https://evil.example.com'})}")
lines.append(f"[api] 未知端点 -> {call('/api/nope', {})}")
status, body = call("/api/favorite", {"id": "xmulibrary", "on": True})
lines.append(f"[api] 收藏 -> {status} {str(body)[:120]}")
status, body = call("/api/favorite", {"id": "xmulibrary", "on": False})
lines.append(f"[api] 取消收藏 -> {status} {str(body)[:120]}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("written")
