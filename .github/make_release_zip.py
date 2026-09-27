# -*- coding: utf-8 -*-
"""把打包好的绿色版目录压成 zip。

单独写成脚本而不是内联 python -c：路径里有中文，还有大量引号嵌套，
内联写法在 workflow 里很容易被 YAML/pwsh 的引号规则吃掉。

用法：python .github/make_release_zip.py <源目录> <输出.zip>
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def say(msg: str) -> None:
    """打印日志，绝不因为控制台编码而抛异常。

    GitHub runner 上 Python 的 stdout 默认是 cp1252，直接 print 中文会
    UnicodeEncodeError 并以退出码 1 结束——构建因此"失败"，但真正的原因
    和压缩本身毫无关系。这里降级到 ASCII 也要把话说完。
    """
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(msg.encode(enc, "replace").decode(enc, "replace"))
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    if len(sys.argv) != 3:
        say("用法: python make_release_zip.py <源目录> <输出.zip>")
        return 2

    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    if not src.is_dir():
        say(f"源目录不存在: {src}")
        return 1

    files = [p for p in sorted(src.rglob("*")) if p.is_file()]
    if not files:
        say(f"源目录是空的: {src}")
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in files:
            # 相对路径，并把分隔符统一成正斜杠
            arc = p.relative_to(src).as_posix()
            # 前面带上目录名，解压后是一个完整文件夹而不是散落一地
            zf.write(p, f"{src.name}/{arc}")

    size_mb = out.stat().st_size / 1024 / 1024
    say(f"已生成 {out.name}：{len(files)} 个文件，{size_mb:.1f} MB")

    # 抽查：确认非 ASCII 名确实带上了 UTF-8 标志位（bit 11）
    with zipfile.ZipFile(out) as zf:
        bad = []
        for info in zf.infolist():
            if not info.filename.isascii() and not (info.flag_bits & 0x800):
                bad.append(info.filename)
        if bad:
            say("警告：以下条目名没有 UTF-8 标志位，解压端可能乱码：")
            for b in bad[:5]:
                say(f"    {b}")
            return 1
        say("条目名 UTF-8 标志位检查：通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
