# -*- coding: utf-8 -*-
"""只看已保存 Key 的"形状"（长度/前后缀/是否含空格），用于判断是不是贴错了东西——绝不打印完整 Key。

用法：python tools/inspect_keys.py
"""
from __future__ import annotations

import json
from pathlib import Path


# --- 仓库根目录，随 clone 位置自适应（原来这里写死了 D:\AI\xmu_hub）---
ROOT = Path(__file__).resolve().parent.parent


CANDIDATES = [
    ROOT / "data" / "userdata.json",
    ROOT / "dist" / "data" / "userdata.json",
    ROOT / "dist" / "厦大统一门户-绿色版" / "data" / "userdata.json",
]


def main() -> None:
    for path in CANDIDATES:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        keys = data.get("aiKeys") or {}
        models = data.get("aiModels") or {}
        print(f"\n{path}")
        print(f"  preferred = {data.get('aiPreferred') or '（未设置）'}")
        if not keys:
            print("  （没有保存任何 Key）")
        for name, value in keys.items():
            value = value or ""
            print(f"  · {name}: 长度={len(value)}｜开头={value[:4]!r}｜结尾={value[-4:]!r}"
                  f"｜有空格={' ' in value}｜有点={'.' in value}｜模型={models.get(name) or '（默认）'}")
        print("  提示：DeepSeek 的 Key 形如 sk- + 32 位小写字母数字；"
              "智谱是 id.secret 两段用点连接；豆包要另填 ep- 开头的接入点 ID。")


if __name__ == "__main__":
    main()
