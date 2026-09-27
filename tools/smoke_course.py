# -*- coding: utf-8 -*-
"""打包版冒烟：确认"数字化教学平台"系列条目已随包发布、分类与网址正确。

用法：先启动打包版（绿色版 exe --no-window），再运行本脚本。
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

# --- 仓库根目录，随 clone 位置自适应（原来这里写死了 D:\AI\xmu_hub）---
ROOT = Path(__file__).resolve().parent.parent


PF = ROOT / "dist" / "厦大统一门户-绿色版" / "data" / "_runtime_port.txt"


def main() -> None:
    port = PF.read_text(encoding="utf-8").strip()
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/catalog", timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    hits = [i for i in data["items"] if "数字化教学平台" in i["name"]]
    print(f"打包版条目数：{len(data['items'])}｜命中 {len(hits)} 条")
    for item in hits:
        print(f"  · {item['name']}")
        print(f"      用途={'/'.join(item['purpose'])}  对象={'/'.join(item['audience'])}  "
              f"精选={item['featured']}  role={item['role']}")
        print(f"      {item['url']}")
        assert item.get("url"), f"{item['name']} 没有网址，点开会没反应"


if __name__ == "__main__":
    main()
