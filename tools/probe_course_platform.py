# -*- coding: utf-8 -*-
"""验证"数字化教学平台"相关网址是否可达、标题是什么（用于写入总集前的核对）。"""
from __future__ import annotations

import re
import ssl
import urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")}

URLS = [
    ("数字化教学平台主站", "https://course.xmu.edu.cn"),
    ("平台简介（现代教育技术中心）", "https://metc.xmu.edu.cn/info/1048/2171.htm"),
    ("学生使用手册", "https://metc.xmu.edu.cn/download/course_student.pdf"),
    ("教师使用手册", "https://metc.xmu.edu.cn/download/course_teacher.pdf"),
    ("毕业论文提交指南（MBA）", "https://mba.xmu.edu.cn/system/_content/download.jsp"
                              "?urltype=news.DownloadAttachUrl&owner=1886773459"
                              "&wbfileid=6742E3F95E75FABEA26834381CA3FB20"),
]


def main() -> None:
    for name, url in URLS:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                        timeout=20, context=CTX) as resp:
                raw = resp.read(9000).decode("utf-8", "ignore")
                title = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
                text = re.sub(r"\s+", " ", title.group(1)).strip() if title else ""
                ctype = resp.headers.get("Content-Type", "")[:30]
                print(f"{name:<22} HTTP {resp.status} | {ctype:<30} | {text[:44]}")
        except Exception as exc:  # noqa: BLE001
            print(f"{name:<22} {type(exc).__name__}: {str(exc)[:70]}")


if __name__ == "__main__":
    main()
