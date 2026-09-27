"""探测免费大模型接口是否可用（应用实际走的网络路径）。"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# --- 仓库根目录，随 clone 位置自适应（原来这里写死了 D:\AI\xmu_hub）---
ROOT = Path(__file__).resolve().parent.parent


OUT = ROOT / "data" / "_free_ai_probe.txt"
lines: list[str] = []


def get(url: str, timeout: int = 40) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "XMUHub/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "ignore")[:300]
    except Exception as exc:  # noqa: BLE001
        return -1, f"{type(exc).__name__}: {exc}"


def post_json(url: str, payload: dict, timeout: int = 60) -> tuple[int, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "User-Agent": "XMUHub/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "ignore")[:300]
    except Exception as exc:  # noqa: BLE001
        return -1, f"{type(exc).__name__}: {exc}"


# 1) Pollinations 简易 GET 接口
q = urllib.parse.quote("用一句话介绍厦门大学")
status, body = get(f"https://text.pollinations.ai/{q}?model=openai")
lines.append(f"[GET text.pollinations.ai] HTTP {status}")
lines.append(f"  body[:300] = {body[:300]!r}")

# 2) Pollinations OpenAI 兼容接口
payload = {
    "model": "openai",
    "messages": [
        {"role": "system", "content": "你是校园导航助手，回答控制在30字内。"},
        {"role": "user", "content": "厦门大学图书馆在哪里预约座位？只回一句话。"},
    ],
}
status2, body2 = post_json("https://text.pollinations.ai/openai", payload)
lines.append(f"\n[POST text.pollinations.ai/openai] HTTP {status2}")
lines.append(f"  body[:400] = {body2[:400]!r}")
if status2 == 200:
    try:
        parsed = json.loads(body2)
        content = parsed["choices"][0]["message"]["content"]
        lines.append(f"  解析出的回答 = {content!r}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"  解析失败：{exc}")

# 3) 备选：DuckDuckGo 的 chat 接口（通常需要 vqd 令牌，先看是否直接可用）
status3, body3 = get("https://duckduckgo.com/duckchat/v1/status")
lines.append(f"\n[GET duckduckgo duckchat status] HTTP {status3} body={body3[:80]!r}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("written")
