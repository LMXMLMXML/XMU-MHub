"""比较免费 AI 各模型的可用性与延迟，用于选默认模型。"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(r"D:\AI\xmu_hub\data\_model_probe.txt")
URL = "https://text.pollinations.ai/openai"

SYSTEM = (
    "你是校园导航助手。只从候选里挑 1 个，用一句中文说明为什么，"
    "回答里直接写入口名称、不要写候选序号。最后单独一行输出：PICK: 序号"
)
USER = (
    "候选入口：\n"
    "1. 名称：厦大后勤｜类型：微信公众号｜入口：微信关注后点我要报修\n"
    "2. 名称：宿舍电费查询｜类型：网站｜网址：elec.xmu.edu.cn\n"
    "3. 名称：财务处｜类型：网站｜网址：cwc.xmu.edu.cn\n\n"
    "用户需求：宿舍水管漏了找谁"
)

lines: list[str] = []
for model in ("openai", "openai-fast", "mistral", "gemini"):
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}],
        "temperature": 0.2,
        "max_tokens": 300,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=payload,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "XMUHub/1.0"},
                                 method="POST")
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        cost = time.time() - start
        text = body["choices"][0]["message"]["content"].strip().replace("\n", " ⏎ ")
        lines.append(f"[{model}] OK 耗时={cost:.1f}s")
        lines.append(f"    {text[:160]}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"[{model}] 失败({time.time() - start:.1f}s)：{type(exc).__name__} {str(exc)[:120]}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("written")
