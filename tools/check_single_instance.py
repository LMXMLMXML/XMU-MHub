# -*- coding: utf-8 -*-
"""验证"单实例复用"探测：端口文件里的实例是否还活着。

用法：先启动一个实例（python app.py --no-window），再运行本脚本。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as hub  # noqa: E402


def main() -> None:
    port_file = hub.PORT_FILE
    try:
        raw = port_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        print(f"读不到端口文件 {port_file}：{exc}")
        return
    alive = hub.existing_instance()
    print(f"端口文件内容：{raw}")
    print(f"探测结果：{alive or '（没有健康实例，将启动新实例）'}")
    if alive:
        print("→ 再次双击 exe 时会直接复用这个实例，不会再起第二个端口")
    else:
        print("→ 现在启动软件会新开一个服务")


if __name__ == "__main__":
    main()
