# -*- coding: utf-8 -*-
"""按名字查看某几条的最终标签，用于快速验证分类规则。

用法：python tools/show_items.py 校园地图 网上展馆 教师主页平台
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "portal.json"


def main() -> None:
    items = {it["name"]: it for it in json.loads(DATA.read_text(encoding="utf-8"))["items"]}
    names = sys.argv[1:] or list(items)[:5]
    for name in names:
        it = items.get(name)
        if not it:
            print(f"· {name}：没有这个条目")
            continue
        print(f"· {name}")
        print(f"    校区={'/'.join(it.get('campus') or [])}  对象={'/'.join(it.get('audience') or [])}")
        print(f"    用途={'/'.join(it.get('purpose') or [])}  形态={it.get('kind')}/{it.get('platform')}  role={it.get('role')}")
        print(f"    说明：{it.get('desc')}")


if __name__ == "__main__":
    main()
