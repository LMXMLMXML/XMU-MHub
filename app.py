"""厦大统一门户 · 桌面端主程序

一个把厦门大学全校网站与小程序按「校区 / 对象 / 用途」统一收口的桌面软件。
点条目一律用系统浏览器打开：该登录就登录、该用哪个内核就用哪个内核。

运行方式：
    python app.py                 # 打开原生窗口（Edge 应用模式，无浏览器边框）
    python app.py --browser       # 用默认浏览器打开
    python app.py --no-window     # 只启动服务并打印地址（调试用）
    python app.py --port 8765     # 指定端口

AI 能力：
    设置环境变量 DEEPSEEK_API_KEY 后，右上角「AI 找入口」由 DeepSeek 驱动；
    未设置时自动降级为本地检索式回答，功能完整可用。

依赖：仅 Python 标准库。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import ssl
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

APP_DIR = Path(__file__).resolve().parent


def resource_dir() -> Path:
    """打包成 exe 后，静态资源在 PyInstaller 的临时解包目录里。"""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", str(Path(sys.executable).parent)))
    return APP_DIR


def user_dir() -> Path:
    """用户数据（收藏/最近）写在 exe 或源码旁边，便于携带。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return APP_DIR


WEB_DIR = resource_dir() / "web"
DATA_FILE = resource_dir() / "data" / "portal.json"
USER_FILE = user_dir() / "data" / "userdata.json"
# 实际监听端口写入该文件，供测试脚本与调试工具读取，
# 避免"端口被旧实例占用→新实例顺延→测试打到旧数据"这类假结果。
PORT_FILE = user_dir() / "data" / "_runtime_port.txt"

DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# 手机 / 平板版的公网网址（把 dist-mobile 传到 Netlify 得到的地址）。
# 桌面版首页会把这一条显示出来，供"发到手机上看"用；换部署地址只改这里
# （或启动时加 --mobile-url），前端不再需要跟着改。
# 注意：/api/open 只放行收录目录里的网址，所以这里显式登记，否则点"在浏览器打开"会被拒。
MOBILE_SITE = "https://whimsical-melomakarona-c3866a.netlify.app/"

CAMPUS_ORDER = ["通用", "思明校区", "翔安校区", "漳州校区", "马来西亚分校"]
AUDIENCE_ORDER = ["全体", "本科生", "研究生", "教师", "校友", "访客/公众"]
PURPOSE_ORDER = ["学习", "科研", "办事", "生活", "资讯", "出行", "其他"]

# ---------------------------------------------------------------- 数据层


def noscheme(url: str) -> str:
    """把 http/https 抹平后的站内地址，用于比对"这条网址在不在收录目录里"。

    目录里收录的是 https://jwc.xmu.edu.cn，而总集里有些行写的是 http 版本；
    不抹平协议的话，点"教务处"会被判成目录外地址直接拒绝。
    """
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    path = (parts.path or "").rstrip("/")
    return f"//{host}{path}"


class Catalog:
    def __init__(self) -> None:
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        self.items: list[dict] = raw["items"]
        self.by_id = {it["id"]: it for it in self.items}
        self.allowed_urls = {it["url"].rstrip("/") for it in self.items if it.get("url")}
        self.allowed_keys = {noscheme(u) for u in self.allowed_urls}

    def facets(self) -> dict:
        def count(field: str) -> dict[str, int]:
            out: dict[str, int] = {}
            for it in self.items:
                # kind / platform / role 是单值字段，其余是标签数组
                if field in ("kind", "platform", "role"):
                    values = [it.get(field, "")]
                else:
                    values = it.get(field, [])
                for v in values:
                    out[v] = out.get(v, 0) + 1
            return out

        return {
            "total": len(self.items),
            "campus": count("campus"),
            "audience": count("audience"),
            "purpose": count("purpose"),
            "kind": count("kind"),
            "platform": count("platform"),
            "role": count("role"),
        }


# ---------------------------------------------------------------- 检索

STOPWORDS = set("的了我想要一个有没有吗呢请问下帮个忙找在哪里怎么如何能不能可以请给出".strip())


def tokenize(text: str) -> list[str]:
    """极简中英混合分词：英文按词，中文按 2-gram + 单字。"""
    text = text.lower()
    tokens: list[str] = []
    for chunk in re.findall(r"[a-z0-9_.]+|[\u4e00-\u9fff]+", text):
        if re.fullmatch(r"[\u4e00-\u9fff]+", chunk):
            tokens.extend(chunk)  # 单字
            tokens.extend(chunk[i:i + 2] for i in range(len(chunk) - 1))  # 2-gram
        else:
            tokens.append(chunk)
    return [t for t in tokens if t and t not in STOPWORDS]


# 按意图扩展查询词：用户说"漏水/坏了"时，实际要找的是报修入口。
# 只靠字面相似度会让"宿舍水管漏了"命中"宿舍水控（热水）"，语义就偏了。
QUERY_HINTS = [
    (("漏", "堵", "坏", "故障", "跳闸", "停水", "停电", "不通", "维修"), ["报修", "维修"]),
    (("借书", "还书", "续借", "查重", "文献"), ["图书馆", "借阅"]),
    (("吃饭", "菜品", "餐厅", "夜宵"), ["食堂", "餐饮"]),
    (("洗澡", "淋浴", "热水"), ["水控", "宿舍"]),
    (("缴费", "学费", "住宿费", "交钱"), ["缴费", "财务"]),
    (("看病", "挂号", "体检", "开药"), ["医院", "门诊"]),
]


def expand_query(query: str, terms: list[str]) -> list[str]:
    """把口语意图补成检索词，只加分不过滤。"""
    for keys, additions in QUERY_HINTS:
        if any(k in query for k in keys):
            for word in additions:
                if word not in terms:
                    terms.append(word)
    return terms


def score_item(item: dict, terms: list[str]) -> float:
    if not terms:
        return 0.0
    name = item["name"].lower()
    keywords = " ".join(item.get("keywords", [])).lower()
    desc = (item.get("desc") or "").lower()
    group = (item.get("group") or "").lower()
    tags = " ".join(item.get("campus", []) + item.get("audience", []) + item.get("purpose", [])).lower()
    entry = (item.get("entry") or "").lower()

    total = 0.0
    for t in terms:
        # 单字命中权重低，避免"报销"被"报名"抢走
        w = 1.0 if len(t) >= 2 else 0.25
        if t in name:
            total += 6.0 * w
        if t in keywords:
            total += 4.0 * w
        if t in tags:
            total += 2.5 * w
        if t in desc:
            total += 2.0 * w
        if t in entry:
            total += 1.5 * w
        if t in group:
            total += 1.0 * w
    # 检索加权：用 hot 而不是 featured —— 首页"精选"只放 7 个，但检索里常用入口
    # 该加的分不能跟着少（否则「报销」62→47 条、「游泳」31→13 条，见 build_data.HOT_URLS）
    #
    # 但必须放在「文本确实命中过」的条件里：否则任何 hot 条目对任何查询都恒定
    # 得 1.2 分，而 search() 的下限 floor 默认 0.0，于是搜 "qqqqqq" 也会返回
    # 满屏结果，"没有匹配的入口"这个空状态两端都永远走不到。
    #
    # role=info 的降权不在这里做，改到 search() 的排序键里（见那儿的说明）。
    if total > 0 and item.get("hot"):
        total += 1.2
    return total


def search_terms(query: str) -> list[str]:
    """检索用词：查询里有 2 字以上的词时丢掉单字。

    单字命中太宽松——"zzzz不存在的词zzzz" 里只有「存」是真命中，
    却能把「云盘存储」「圈存机」「数字校园卡(圈存)」全捞出来。
    而 2-gram 分词保证真实中文词至少有一个 2 字词，丢掉单字不会漏召回；
    只有查询本身就是单字时（"书"）才保留，不然查不出东西。
    """
    terms = tokenize(query)
    multi = [t for t in terms if len(t) >= 2]
    return multi if multi else terms


def search(catalog: Catalog, query: str, campus: str = "", audience: str = "",
           purpose: str = "", kind: str = "", platform: str = "", limit: int = 60,
           floor: float = 0.0) -> list[dict]:
    # 输入里有内容、却切不出任何检索词（纯标点 "？？？"、纯停用词 "的的的"），
    # 说明用户确实在搜、只是没有可用关键词。此时必须返回空结果，
    # 不能落到下面「terms 为空 = 没传查询」那条分支去，否则会把整个目录倒出来。
    if query.strip() and not tokenize(query):
        return []
    terms = expand_query(query, search_terms(query))
    results = []
    for item in catalog.items:
        if campus and campus not in item.get("campus", []) and "通用" not in item.get("campus", []):
            continue
        if audience and audience not in item.get("audience", []) and "全体" not in item.get("audience", []):
            continue
        if purpose and purpose not in item.get("purpose", []):
            continue
        if kind and item.get("kind") != kind:
            continue
        if platform and item.get("platform") not in (platform, "both"):
            continue
        s = score_item(item, terms) if terms else 0.0
        if terms and s <= floor:
            continue
        # 选中校区/对象时，专属条目优先于全校通用条目
        specific = 1 if (campus and campus in item.get("campus", [])) else 0
        specific += 1 if (audience and audience in item.get("audience", [])) else 0
        results.append((s, specific, item))
    # 排序键里的 role=info 降权：纯说明页/公告（role=info）排在"打开就能办事"的
    # 功能入口之后，但仍然保留在结果里。
    # 原先这个 -2.0 写在 score_item 里，会被 s <= floor 当成"不相关"直接剔掉——
    # 例如「师资」只命中 desc（+2.0），再减 2.0 恰好等于 0，条目就消失了。
    # 降权是排序意图，不该兼职做过滤。
    results.sort(key=lambda row: (
        -row[0],
        row[2].get("role") == "info",
        -row[1],
        not row[2].get("hot"),
        row[2]["name"],
    ))
    return [item for _, _, item in results[:limit]]


def strong_match(item: dict, terms: list[str]) -> bool:
    """要求命中至少一个多字词，避免只靠单字擦边。

    只匹配条目自身的名称/关键词/说明/入口；身份与用途标签不参与，
    否则所有挂「研究生」标签的重点实验室都会被当成相关结果。
    """
    fields = " ".join([
        item.get("name", ""),
        " ".join(item.get("keywords", [])),
        item.get("desc") or "",
        item.get("entry") or "",
    ]).lower()
    return any(len(t) >= 2 and t in fields for t in terms)


def ai_candidates(catalog: Catalog, question: str, inferred: dict, limit: int = 12) -> list[dict]:
    """给 AI 挑候选：文本相关性为主，身份/校区/用途/端只做加分。

    早期版本把这些属性当硬过滤，导致"我手机上怎么查成绩"把电脑端入口全筛掉、
    "校友进校"把访客类入口筛掉，AI 只能回答"没有匹配到"。
    """
    terms = expand_query(question, tokenize(question))
    rows: list[tuple[float, dict]] = []
    for item in catalog.items:
        base = score_item(item, terms)
        if base <= 0 or not strong_match(item, terms):
            continue
        score = base
        if inferred.get("campus") and inferred["campus"] in item.get("campus", []):
            score += 2.0
        if inferred.get("audience") and (
            inferred["audience"] in item.get("audience", []) or "全体" in item.get("audience", [])
        ):
            score += 1.2
        if inferred.get("purpose") and inferred["purpose"] in item.get("purpose", []):
            score += 1.2
        if inferred.get("platform") and item.get("platform") in (inferred["platform"], "both"):
            score += 1.0
        rows.append((score, item))

    if len(rows) < 3:
        # 放宽：不要求命中多字词
        for item in catalog.items:
            base = score_item(item, terms)
            if base > 0:
                rows.append((base, item))

    rows.sort(key=lambda row: -row[0])
    return [item for _, item in rows[:limit]]


def infer_filters(question: str) -> dict:
    """从口语化提问里推断校区 / 身份 / 用途，用于收窄 AI 候选范围。"""
    campus = ""
    for key, value in (("翔安", "翔安校区"), ("漳州", "漳州校区"),
                       ("马来西亚", "马来西亚分校"), ("思明", "思明校区")):
        if key in question:
            campus = value
            break

    audience = ""
    for keys, value in (
        (("研究生", "硕士", "博士", "读研", "导师", "开题", "答辩"), "研究生"),
        (("本科生", "本科", "大一", "大二", "大三", "大四", "选课", "辅修", "保研"), "本科生"),
        (("老师", "教师", "教工", "青椒", "备课", "职称", "报账", "人事"), "教师"),
        (("校友", "返校", "毕业多年", "校友卡"), "校友"),
        (("访客", "游客", "参观", "进校", "入校"), "访客/公众"),
    ):
        if any(k in question for k in keys):
            audience = value
            break

    purpose = ""
    for keys, value in (
        (("报修", "宿舍", "食堂", "吃饭", "洗衣", "快递", "班车", "校车", "电费", "校园卡",
          "饭卡", "一卡通", "医院", "看病", "挂号", "体育", "游泳", "健身", "场馆", "理发"), "生活"),
        (("成绩", "课表", "选课", "论文", "考试", "四六级", "教材", "上课", "学习", "作业",
          "绩点", "查重", "学位", "讲座", "借书", "图书馆"), "学习"),
        (("报销", "报账", "缴费", "学费", "发票", "采购", "招标", "盖章", "用印", "证明",
          "档案", "办证", "请假", "入职", "办事"), "办事"),
        (("科研", "实验室", "仪器", "基金", "专利", "项目", "超算", "算力"), "科研"),
        (("新闻", "校历", "校史", "展馆", "地图"), "资讯"),
    ):
        if any(k in question for k in keys):
            purpose = value
            break

    platform = ""
    if any(k in question for k in ("手机", "微信", "小程序", "公众号", "扫码", "APP", "app")):
        platform = "mobile"
    elif any(k in question for k in ("电脑", "网页", "浏览器", "pc", "PC", "电脑端")):
        platform = "pc"

    return {"campus": campus, "audience": audience, "purpose": purpose, "platform": platform}


# ---------------------------------------------------------------- 用户数据


class UserData:
    def __init__(self) -> None:
        self.path = USER_FILE
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}
        else:
            self.data = {}
        self.data.setdefault("favorites", [])
        self.data.setdefault("recent", [])
        self.data.setdefault("history", [])
        self.data.setdefault("aiLocalModel", "")
        # 首次打开时问一次的"校区 + 身份"，之后作为默认筛选（取代原来的两排筛选）
        self.data.setdefault("profile", {})
        # 界面只配置"本机模型"，密钥不再落盘（环境变量仍然支持，供进阶用户使用）
        _MODEL_STORE.clear()
        saved_model = str(self.data.get("aiLocalModel") or "").strip()
        if saved_model:
            _MODEL_STORE["ollama"] = saved_model
            _PREFERRED["provider"] = "ollama"

    def set_ai_local_model(self, model: str) -> None:
        self.data["aiLocalModel"] = model or ""
        self.save()

    def set_profile(self, profile: dict) -> dict:
        allowed_campus = {"", "通用", "思明校区", "翔安校区", "漳州校区", "马来西亚分校"}
        allowed_audience = {"", "全体", "本科生", "研究生", "教师", "校友", "访客/公众"}
        campus = str(profile.get("campus") or "")
        audience = str(profile.get("audience") or "")
        self.data["profile"] = {
            "campus": campus if campus in allowed_campus else "",
            "audience": audience if audience in allowed_audience else "",
            "asked": bool(profile.get("asked", True)),
            "skipped": bool(profile.get("skipped", False)),
        }
        self.save()
        return self.data["profile"]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")

    def toggle_favorite(self, item_id: str, on: bool | None = None) -> list[str]:
        favs: list[str] = self.data["favorites"]
        if on is True and item_id not in favs:
            favs.append(item_id)
        elif on is False and item_id in favs:
            favs.remove(item_id)
        elif on is None:
            favs.remove(item_id) if item_id in favs else favs.append(item_id)
        self.save()
        return favs

    def touch(self, item_id: str) -> list[str]:
        recent: list[str] = self.data["recent"]
        if item_id in recent:
            recent.remove(item_id)
        recent.insert(0, item_id)
        del recent[12:]
        self.save()
        return recent

    def record_search(self, query: str) -> list[str]:
        """记录搜索词：去重、最新在前、最多 12 条。"""
        query = query.strip()
        history: list[str] = self.data["history"]
        if len(query) < 2:
            return history
        if query in history:
            history.remove(query)
        history.insert(0, query)
        del history[12:]
        self.save()
        return history

    def clear_search(self) -> list[str]:
        self.data["history"] = []
        self.save()
        return []


# ---------------------------------------------------------------- 大模型接入

# 注意：要兼容弯引号（doesn’t）与连字符（top-up），否则漏判会把账单提示当成答案
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

PROVIDER_ERROR_MARKERS = (
    "enough credits", "top-up", "top up", "insufficient", "unauthorized",
    "invalid api key", "please register", "quota", "rate limit",
    "额度不足", "余额不足", "配额", "注册后",
)

# 多个引擎按顺序自动降级：谁有 Key 用谁；一个 Key 都没有就直接走本地检索（不再有免密钥的公共免费档）。
# 全部是 OpenAI 兼容接口，所以调用代码只有一份。
# Key 优先取"界面上填的"（存在 data/userdata.json），其次才是环境变量；豆包要填推理接入点 ID。
PROVIDERS = {
    "deepseek": {
        "label": "DeepSeek",
        "url": DEEPSEEK_ENDPOINT,
        "model": DEEPSEEK_MODEL,
        "env": "DEEPSEEK_API_KEY",
        "model_env": "XMUHUB_DEEPSEEK_MODEL",
        "note": "中文强、便宜，推荐首选",
    },
    "zhipu": {
        "label": "智谱 GLM",
        "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model": "glm-4-flash",
        "env": "ZHIPU_API_KEY",
        "model_env": "XMUHUB_ZHIPU_MODEL",
        "note": "glm-4-flash 免费档，零成本",
    },
    "dashscope": {
        "label": "通义千问",
        "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": "qwen-turbo",
        "env": "DASHSCOPE_API_KEY",
        "model_env": "XMUHUB_QWEN_MODEL",
        "note": "阿里云百炼，新用户有免费额度",
    },
    "siliconflow": {
        "label": "硅基流动",
        "url": "https://api.siliconflow.cn/v1/chat/completions",
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "env": "SILICONFLOW_API_KEY",
        "model_env": "XMUHUB_SF_MODEL",
        "note": "聚合站，部分开源模型免费",
    },
    "moonshot": {
        "label": "Kimi",
        "url": "https://api.moonshot.cn/v1/chat/completions",
        "model": "moonshot-v1-8k",
        "env": "MOONSHOT_API_KEY",
        "model_env": "XMUHUB_MOONSHOT_MODEL",
        "note": "长文本见长",
    },
    "ark": {
        "label": "豆包",
        "url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "model": os.environ.get("XMUHUB_ARK_MODEL", ""),
        "env": "ARK_API_KEY",
        "model_env": "XMUHUB_ARK_MODEL",
        "note": "火山方舟，model 要填接入点 ID（ep-...）",
    },
    "ollama": {
        "label": "本地模型",
        "url": os.environ.get("XMUHUB_OLLAMA_URL", "http://127.0.0.1:11434/v1/chat/completions"),
        "model": os.environ.get("XMUHUB_OLLAMA_MODEL", "qwen2.5:3b"),
        "env": "",
        "model_env": "XMUHUB_OLLAMA_MODEL",
        "note": "本机 Ollama，完全离线、零成本，无需 Key",
    },
}

# 降级顺序：便宜好用的放前面；本地 Ollama 兜底；都没有 Key 时直接走本地检索
CHAIN_ORDER = ["deepseek", "zhipu", "dashscope", "siliconflow", "moonshot", "ark", "ollama"]

# 界面只配置"本机模型"；大模型密钥一律走环境变量（不落盘）
_KEY_STORE: dict[str, str] = {}
_PREFERRED: dict[str, str] = {"provider": ""}

_ANSWER_CACHE: dict[str, dict] = {}
_CACHE_LIMIT = 60
_OLLAMA_CACHE: dict[str, float] = {}
# 界面上可以自己改模型名（豆包必须填接入点 ID，智谱/通义也常常要换型号）
_MODEL_STORE: dict[str, str] = {}


def provider_model(name: str) -> str:
    conf = PROVIDERS[name]
    return (_MODEL_STORE.get(name)
            or os.environ.get(conf.get("model_env", ""), "").strip()
            or conf["model"])


def provider_key(name: str) -> str:
    """界面里填的 Key 优先，其次读环境变量。"""
    conf = PROVIDERS[name]
    if _KEY_STORE.get(name):
        return _KEY_STORE[name].strip()
    env_name = conf.get("env", "")
    return os.environ.get(env_name, "").strip() if env_name else ""


def friendly_ai_error(status: int, body: str) -> str:
    """把各家五花八门的报错翻译成一句人话。"""
    low = (body or "").lower()
    if status in (401, 403) or "invalid api key" in low or "authentication" in low \
            or "令牌" in body or "unauthorized" in low:
        return "Key 无效或已过期（请检查是否复制完整、是否有空格）"
    if status == 402 or "insufficient" in low or "balance" in low or "余额" in body or "额度" in body:
        return "Key 有效但账户余额/额度不足"
    if status == 429 or "rate limit" in low or "too many" in low:
        return "请求太频繁（触发限流），稍后再试"
    if status == 404 or "model" in low and "not" in low:
        return "模型名不对（例如豆包必须填接入点 ID：ep-...）"
    if status == 400:
        return "请求被拒绝（常见原因：模型名不对，或该 Key 没有开通这个模型）"
    if status >= 500:
        return "对方服务器故障，稍后再试"
    return "调用失败"


def validate_provider(name: str, key: str | None = None, model: str | None = None) -> dict:
    """拿最小的请求试一下这个引擎到底能不能用（保存 Key 时立刻验证）。"""
    if name not in PROVIDERS:
        return {"ok": False, "message": "未知的引擎"}
    conf = PROVIDERS[name]
    use_key = (key if key is not None else provider_key(name)).strip()
    use_model = (model or provider_model(name)).strip()
    if conf.get("env") and not use_key:
        return {"ok": False, "status": 0, "message": "没有填 Key", "model": use_model}
    if not use_model:
        return {"ok": False, "message": "没有填模型名（豆包要填接入点 ID）"}

    payload = json.dumps({
        "model": use_model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "temperature": 0,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "XMUHub/1.0"}
    if use_key:
        headers["Authorization"] = f"Bearer {use_key}"
    req = urllib.request.Request(conf["url"], data=payload, headers=headers, method="POST")
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read(200)
            return {"ok": True, "message": f"验证通过（{time.time() - started:.1f}s）",
                    "model": use_model, "latency": round(time.time() - started, 2)}
    except urllib.error.HTTPError as exc:
        body = exc.read(200).decode("utf-8", "ignore")
        return {"ok": False, "status": exc.code, "message": friendly_ai_error(exc.code, body),
                "detail": body[:160], "model": use_model}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": 0, "model": use_model,
                "message": f"连不上（{type(exc).__name__}）：请检查网络或代理设置"}


def provider_ready(name: str) -> bool:
    """这个引擎现在可用吗：有 Key / 本地 Ollama 在跑 / 免密钥引擎。"""
    conf = PROVIDERS[name]
    if conf.get("env") or name in _KEY_STORE:
        return bool(provider_key(name))
    if name == "ollama":
        now = time.time()
        if _OLLAMA_CACHE.get("checked_at", 0) > now - 60:
            return bool(_OLLAMA_CACHE.get("ok"))
        ok = False
        try:
            req = urllib.request.Request(conf["url"].replace("/chat/completions", "/models"),
                                         headers={"User-Agent": "XMUHub/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                ok = resp.status == 200
        except Exception:  # noqa: BLE001 - 没装/没启动就当不可用
            ok = False
        _OLLAMA_CACHE.update({"ok": ok, "checked_at": now})
        return ok
    return True


def provider_chain() -> list[str]:
    """返回本次要依次尝试的引擎列表（末尾一定是 local 兜底）。"""
    override = os.environ.get("XMUHUB_AI", "").strip().lower()
    if override in ("local", "off"):
        return ["local"]
    if override in PROVIDERS:
        return [override, "local"]
    preferred = _PREFERRED.get("provider", "")
    ready = [name for name in CHAIN_ORDER if provider_ready(name)]
    if preferred in ready:                      # 用户指定了优先引擎
        ready = [preferred] + [n for n in ready if n != preferred]
    return (ready or []) + ["local"]


def ai_catalog() -> list[dict]:
    """给设置面板用的引擎清单（绝不回传 Key 明文）。"""
    out = []
    for name in CHAIN_ORDER:
        conf = PROVIDERS[name]
        key = provider_key(name)
        out.append({
            "id": name,
            "label": conf["label"],
            "model": provider_model(name),
            "note": conf.get("note", ""),
            "needsKey": bool(conf.get("env")),
            "hasKey": bool(key),
            "ready": provider_ready(name),
            "keyHint": (key[:4] + "…" + key[-4:]) if len(key) >= 12 else ("已设置" if key else ""),
        })
    return out


def ollama_status() -> dict:
    """本机 Ollama 的状态：装了吗、在跑吗、有哪些模型。

    这是唯一"永久免费、不需要 Key"的 AI 路子——模型跑在用户自己电脑上。
    """
    base = PROVIDERS["ollama"]["url"].replace("/v1/chat/completions", "")
    info = {"base": base, "running": False, "installed": False, "models": [],
            "current": provider_model("ollama")}
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        info["running"] = True
        info["installed"] = True
        info["models"] = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:  # noqa: BLE001 - 没装/没启动都走这里
        info["installed"] = bool(shutil.which("ollama"))
    return info


# ---------------------------------------------------------------- 一键下载（模型 / 安装包）

# 推荐模型：按"体积小 → 效果好"排，标注大概体积与适合谁
LOCAL_MODELS = [
    {"id": "qwen2.5:1.5b", "size": "约 1 GB", "note": "最快，老电脑也跑得动"},
    {"id": "qwen2.5:3b", "size": "约 2 GB", "note": "推荐：速度与质量平衡"},
    {"id": "qwen2.5:7b", "size": "约 4.7 GB", "note": "效果最好，内存 ≥ 16G 再选"},
]

OLLAMA_SETUP_URL = "https://ollama.com/download/OllamaSetup.exe"
# 官方源与 GitHub 直连在国内常被墙（实测 15s 超时），所以按"加速源优先"自动回退。
# 所有地址指向同一个官方安装包（GitHub Releases 的 OllamaSetup.exe，约 1.57 GB）。
_SETUP_GH = "https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe"
OLLAMA_SOURCES: list[tuple[str, str]] = [
    ("gh-proxy.com 加速", "https://gh-proxy.com/" + _SETUP_GH),
    ("ghproxy.net 加速", "https://ghproxy.net/" + _SETUP_GH),
    ("GitHub 直连", _SETUP_GH),
    ("官方站点", OLLAMA_SETUP_URL),
]
SETUP_SIZE_HINT = "约 1.57 GB"

_PULL: dict = {"state": "idle", "model": "", "status": "", "completed": 0, "total": 0,
               "percent": 0, "error": "", "started": 0.0}
_PULL_LOCK = threading.Lock()
_INSTALL: dict = {"state": "idle", "received": 0, "total": 0, "percent": 0,
                  "path": "", "error": ""}
_INSTALL_LOCK = threading.Lock()


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} GB"


def pull_progress() -> dict:
    with _PULL_LOCK:
        snap = dict(_PULL)
    snap["completedText"] = _human(snap.get("completed", 0))
    snap["totalText"] = _human(snap.get("total", 0))
    return snap


def start_model_pull(model: str) -> dict:
    """在本机后台把模型拉下来（转发 Ollama 的 /api/pull 流并统计进度）。"""
    model = (model or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._:\-/]{2,60}", model):
        return {"ok": False, "error": "模型名不合法"}
    with _PULL_LOCK:
        if _PULL["state"] == "running":
            return {"ok": False, "error": f"正在下载 {_PULL['model']}，请先等它下完"}
        _PULL.update({"state": "running", "model": model, "status": "准备中…",
                      "completed": 0, "total": 0, "percent": 0, "error": "",
                      "started": time.time()})
    threading.Thread(target=_pull_worker, args=(model,), daemon=True).start()
    return {"ok": True, "progress": pull_progress()}


def _pull_worker(model: str) -> None:
    base = PROVIDERS["ollama"]["url"].replace("/v1/chat/completions", "")
    layers: dict[str, list[int]] = {}          # digest -> [completed, total]
    try:
        payload = json.dumps({"model": model, "stream": True}).encode("utf-8")
        req = urllib.request.Request(f"{base}/api/pull", data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=1800) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "ignore").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if obj.get("error"):
                    raise RuntimeError(str(obj["error"]))
                status = str(obj.get("status") or "")
                digest = str(obj.get("digest") or "")
                if digest and ("total" in obj or "completed" in obj):
                    completed, total = layers.get(digest, [0, 0])
                    layers[digest] = [int(obj.get("completed") or completed),
                                      int(obj.get("total") or total)]
                done = sum(v[0] for v in layers.values())
                allb = sum(v[1] for v in layers.values())
                percent = int(done * 100 / allb) if allb else 0
                with _PULL_LOCK:
                    # 运行中最多显示 99%：Ollama 逐层上报，后面的层出现时总量才变大，
                    # 直接给 100% 会让进度条"提前跑满"；真实字节数（X / Y）照实显示
                    _PULL.update({"status": status or _PULL["status"], "completed": done,
                                  "total": allb, "percent": min(percent, 99)})
                if status == "success":
                    with _PULL_LOCK:
                        _PULL.update({"state": "done", "percent": 100,
                                      "status": f"{model} 已下载完成"})
                    return
        with _PULL_LOCK:
            _PULL.update({"state": "done", "percent": 100, "status": f"{model} 已就绪"})
    except Exception as exc:  # noqa: BLE001
        with _PULL_LOCK:
            _PULL.update({"state": "error", "error": f"{type(exc).__name__}: {exc}",
                          "status": "下载失败"})


def install_progress() -> dict:
    with _INSTALL_LOCK:
        snap = dict(_INSTALL)
    snap["receivedText"] = _human(snap.get("received", 0))
    snap["totalText"] = _human(snap.get("total", 0))
    return snap


def reachable(url: str, timeout: int = 8) -> tuple[bool, int]:
    """HEAD 一下，返回 (是否可用, 文件大小)。"""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "XMUHub/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return False, 0
            return True, int(resp.headers.get("Content-Length") or 0)
    except Exception:  # noqa: BLE001
        return False, 0


def pick_setup_source() -> tuple[str, str, int]:
    """挑一个能下得动的安装包源（国内直连官方/GitHub 常被墙，所以加速源优先）。"""
    for name, url in OLLAMA_SOURCES:
        ok, size = reachable(url)
        if ok and size > 10_000_000:
            return name, url, size
    return "", "", 0


def start_ollama_installer(custom_url: str = "") -> dict:
    """下载官方安装包到"下载"目录（**不静默安装**，装不装由用户决定）。"""
    with _INSTALL_LOCK:
        if _INSTALL["state"] == "running":
            return {"ok": False, "error": "安装包正在下载中（可先等它下完或重启软件）"}
        _INSTALL.update({"state": "running", "received": 0, "total": 0, "percent": 0,
                         "path": "", "error": "", "source": "正在挑选可用下载源…"})
    threading.Thread(target=_installer_worker, args=(custom_url.strip(),), daemon=True).start()
    return {"ok": True, "progress": install_progress()}


def _installer_worker(custom_url: str = "") -> None:
    """按顺序尝试各下载源；某个源失败就换下一个（HEAD 通过不代表 GET 一定能下）。"""
    sources = [("自定义地址", custom_url)] if custom_url else list(OLLAMA_SOURCES)
    tried: list[str] = []

    def writable_dir(path: Path) -> bool:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".xmuhub_write_test"
            probe.write_bytes(b"ok")
            probe.unlink()
            return True
        except OSError:
            return False

    target_dir = next((d for d in (Path(os.path.expanduser("~")) / "Downloads",
                                    Path(os.path.expanduser("~")),
                                    APP_DIR / "downloads") if writable_dir(d)), None)
    if target_dir is None:
        with _INSTALL_LOCK:
            _INSTALL.update({"state": "error", "error": "找不到可写目录来保存安装包"})
        return
    target = target_dir / "OllamaSetup.exe"

    try:
        for name, url in sources:
            with _INSTALL_LOCK:
                _INSTALL.update({"source": f"检测 {name}…", "received": 0, "percent": 0})
            ok, size = reachable(url)
            if not ok or size < 10_000_000:
                tried.append(f"{name}（连不上）")
                continue
            try:
                with _INSTALL_LOCK:
                    _INSTALL.update({"source": name, "total": size, "received": 0, "percent": 0})
                req = urllib.request.Request(url, headers={"User-Agent": "XMUHub/1.0"})
                with urllib.request.urlopen(req, timeout=900) as resp, open(target, "wb") as fh:
                    total = int(resp.headers.get("Content-Length") or size)
                    received = 0
                    while True:
                        chunk = resp.read(262144)
                        if not chunk:
                            break
                        fh.write(chunk)
                        received += len(chunk)
                        with _INSTALL_LOCK:
                            _INSTALL.update({"received": received, "total": total,
                                             "percent": int(received * 100 / total) if total else 0})
                with _INSTALL_LOCK:
                    _INSTALL.update({"state": "done", "percent": 100, "path": str(target)})
                return
            except Exception as exc:  # noqa: BLE001 - 这个源不行，换下一个
                tried.append(f"{name}（{type(exc).__name__}）")
                continue
        with _INSTALL_LOCK:
            _INSTALL.update({
                "state": "error",
                "error": ("所有下载源都失败了（" + "、".join(tried) + "）。"
                          "可挂代理后在下面填一个能用的安装包地址。"),
            })
    except Exception as exc:  # noqa: BLE001
        with _INSTALL_LOCK:
            _INSTALL.update({"state": "error", "error": f"{type(exc).__name__}: {exc}"})


def start_ollama_service() -> dict:
    """启动本机 Ollama 服务（装完但没在跑时用）。"""
    exe = shutil.which("ollama") or ""
    if not exe:
        return {"ok": False, "error": "没找到 ollama 命令，请先安装"}
    try:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen([exe, "serve"], creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"启动失败：{exc}"}
    for _ in range(10):                     # 等它就绪（最多 5 秒）
        time.sleep(0.5)
        if ollama_status()["running"]:
            return {"ok": True, "local": ollama_status()}
    return {"ok": False, "error": "已尝试启动，但服务还没就绪（可稍后点重新检测）"}


def use_ollama_model(model: str) -> dict:
    """把本机某个模型设为当前引擎（不需要 Key，永久可用）。"""
    model = (model or "").strip()
    if not model:
        return {"ok": False, "error": "没有选择模型"}
    _MODEL_STORE["ollama"] = model
    _PREFERRED["provider"] = "ollama"
    _OLLAMA_CACHE.clear()          # 让就绪状态立刻重算
    if hasattr(Handler, "userdata") and Handler.userdata is not None:
        Handler.userdata.set_ai_local_model(model)
    return {"ok": True, "verify": validate_provider("ollama", None, model),
            "local": ollama_status(), "providers": ai_catalog()}


def choose_provider() -> str:
    """用于展示：第一个真正可用的引擎。"""
    return provider_chain()[0]


def provider_status() -> dict:
    chain = provider_chain()
    name = chain[0]
    if name == "local":
        return {"provider": "local", "label": "本地检索", "model": "-", "chain": chain,
                "chainLabels": ["本地检索"], "providers": ai_catalog(),
                "preferred": _PREFERRED["provider"]}
    conf = PROVIDERS[name]
    return {
        "provider": name,
        "label": conf["label"],
        "model": provider_model(name),
        "chain": chain,
        "chainLabels": [PROVIDERS[c]["label"] if c in PROVIDERS else "本地检索" for c in chain],
        "providers": ai_catalog(),
        "preferred": _PREFERRED["provider"],
    }


def build_messages(question: str, candidates: list[dict], history: list[dict],
                   inferred: dict | None = None) -> list[dict]:
    lines = []
    for i, it in enumerate(candidates, 1):
        lines.append(
            f"{i}. 名称：{it['name']}｜类型：{it['kindLabel']}｜端：{it.get('platformLabel') or '—'}"
            f"｜网址：{it.get('url') or '（无网址）'}｜入口：{it.get('entry') or '—'}"
            f"｜分类：{'/'.join(it.get('purpose', []))}｜对象：{'/'.join(it.get('audience', []))}"
            f"｜简介：{it.get('desc') or '—'}"
        )
    context = "\n".join(lines)

    system = (
        "你是厦门大学校园服务导航助手。用户会用口语描述需求，你要从给定的候选入口中挑选最合适的 1-3 个，"
        "用简洁中文回答。要求：\n"
        "1) 直接说“推荐 X”，并说明为什么适合（结合用户身份/校区/端）；\n"
        "2) 只能推荐候选列表里出现过的入口，绝不编造名称或网址；\n"
        "3) 候选列表已经过相关性预筛，通常都有可用答案；除非候选确实完全不相关，"
        "否则不要回答“没有匹配到”，应优先给出最接近的推荐；\n"
        "4) 涉及小程序时，提醒“小程序需在微信里搜索名称打开”；\n"
        "5) 回答里直接写入口名称，不要写候选序号；\n"
        "6) 回答控制在 120 字以内，不要用 Markdown 标题。\n"
        "最后单独一行输出：PICK: 序号,序号"
    )
    messages = [{"role": "system", "content": system}]
    for turn in history[-4:]:
        messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})

    hints = []
    if inferred:
        label_map = {"audience": "用户身份", "purpose": "用途", "campus": "校区", "platform": "使用端"}
        for key, label in label_map.items():
            if inferred.get(key):
                hints.append(f"{label}={inferred[key]}")
    hint_text = ("\n（系统已推断：" + "，".join(hints) + "；请优先推荐与这些条件匹配的入口）") if hints else ""

    messages.append({
        "role": "user",
        "content": f"候选入口：\n{context}\n\n用户需求：{question}{hint_text}",
    })
    return messages


def call_llm(provider: str, messages: list[dict]) -> tuple[bool, str, str]:
    """返回 (是否成功, 回答文本, 失败原因)。"""
    conf = PROVIDERS[provider]
    key = provider_key(provider)
    if conf.get("env") and not key:
        return False, "", f"{conf['label']} 未配置 Key"

    payload = json.dumps({
        "model": provider_model(provider),
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 500,
        "stream": False,
    }).encode("utf-8")

    headers = {"Content-Type": "application/json", "User-Agent": "XMUHub/1.0"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    req = urllib.request.Request(conf["url"], data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        text = body["choices"][0]["message"]["content"].strip()
        # 免费接口有时会以 200 返回"额度/注册"之类的提示文本，那不是对用户问题的回答，
        # 必须当成失败走本地兜底，否则用户会看到一段账单提示。
        lowered = text.lower()
        if any(marker in lowered for marker in PROVIDER_ERROR_MARKERS):
            return False, "", f"{conf['label']} 额度或账号异常：{text[:120]}"
        return True, text, ""
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:200]
        return False, "", f"{conf['label']} 接口返回 {exc.code}：{detail}"
    except Exception as exc:  # noqa: BLE001
        return False, "", f"调用 {conf['label']} 失败：{exc}"


def llm_ask(question: str, candidates: list[dict], history: list[dict], inferred: dict | None = None) -> dict:
    chain = provider_chain()
    if chain[0] == "local":
        return {"ok": False, "reason": "已切换为本地检索模式"}

    tried: list[str] = []
    errors: list[str] = []
    for provider in chain:
        if provider == "local":
            break
        cache_key = f"{provider}|{question}"
        if cache_key in _ANSWER_CACHE:
            cached = dict(_ANSWER_CACHE[cache_key])
            cached["cached"] = True
            return cached

        ok, text, error = call_llm(provider, build_messages(question, candidates, history, inferred))
        tried.append(provider)
        if not ok:
            errors.append(error)
            continue        # 这个引擎不行，自动换下一个

        picks: list[int] = []
        match = re.search(r"PICK:\s*([0-9,\s]+)", text)
        if match:
            picks = [int(x) for x in re.findall(r"\d+", match.group(1))]
            text = text[:match.start()].strip()
        chosen = [candidates[i - 1]["id"] for i in picks if 1 <= i <= len(candidates)]

        # 模型偶尔会"拒答"：候选其实是相关的，但它回了"没有匹配到"。
        # 这时以本地检索结果为准，避免回答与下方推荐按钮自相矛盾。
        refusal = ("没有匹配到", "没有找到", "未找到", "无法找到", "没有合适", "没有相关")
        if not chosen and candidates and any(p in text for p in refusal):
            text = local_answer(question, candidates)["answer"]
            chosen = [it["id"] for it in candidates[:3]]

        result = {
            "ok": True,
            "answer": text,
            "items": chosen,
            "engine": provider,
            "label": PROVIDERS[provider]["label"],
            "model": provider_model(provider),
            "tried": tried,
        }
        if len(_ANSWER_CACHE) >= _CACHE_LIMIT:
            _ANSWER_CACHE.pop(next(iter(_ANSWER_CACHE)))
        _ANSWER_CACHE[cache_key] = dict(result)
        return result

    return {"ok": False, "reason": "；".join(errors) or "没有可用的 AI 引擎", "tried": tried}


def local_answer(question: str, candidates: list[dict], reason: str = "") -> dict:
    if not candidates:
        return {
            "ok": True,
            "engine": "local",
            "answer": "没有找到匹配的入口。可以换个说法，例如「研究生查成绩」「宿舍报修」「预约进校」。",
            "items": [],
            "note": reason,
        }
    top = candidates[:3]
    parts = []
    for it in top:
        how = it.get("entry") or it.get("url") or ""
        parts.append(f"「{it['name']}」（{it['kindLabel']}）{'：' + how if how else ''}")
    answer = "本地检索到相关入口：" + "；".join(parts) + "。"
    if any(not it.get("url") for it in top):
        answer += "小程序需在微信里搜索名称打开。"
    return {
        "ok": True,
        "engine": "local",
        "answer": answer,
        "items": [it["id"] for it in top],
        "note": reason,
    }


# ------------------------------------------------- 把浏览器窗口提到软件前面

# 我们自己就是一个 Edge 应用模式窗口（标题是页面的 <title>），
# 提窗口时必须把它排除掉，否则"提到前面"的会变成软件自己。
APP_WINDOW_TITLE = "厦大统一门户"
_BROWSER_EXES = {
    "chrome.exe", "msedge.exe", "firefox.exe", "iexplore.exe", "brave.exe",
    "opera.exe", "vivaldi.exe", "chromium.exe", "arc.exe",
    "360se.exe", "360chrome.exe", "sogouexplorer.exe", "qqbrowser.exe", "maxthon.exe",
}
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def browser_windows() -> list[int]:
    """列出当前所有"浏览器窗口"的句柄（按 Z 序，最上面的排最前）。

    排除两样东西：软件自己的窗口（标题以「厦大统一门户」开头），
    以及没有标题的隐形窗口。非 Windows 直接返回空表。
    """
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    found: list[int] = []

    def proc_name(pid: int) -> str:
        handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value).lower()
            return ""
        finally:
            kernel32.CloseHandle(handle)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if not title or title.startswith(APP_WINDOW_TITLE):
            return True                     # 软件自己的窗口，跳过
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if proc_name(pid.value) in _BROWSER_EXES:
            found.append(int(hwnd))
        return True

    user32.EnumWindows(enum_proc, 0)
    return found


def raise_window(hwnd: int) -> bool:
    """把一个窗口从最小化恢复并提到最前。

    Windows 默认不许后台进程抢前台（只会任务栏闪一下）。先直接试一次；
    被前台锁挡住时，才补一次 ALT 轻敲再试——这是绕开前台锁的常规做法，
    用户看不到界面变化，也不会平白无故往系统里塞按键。
    """
    if sys.platform != "win32" or not hwnd:
        return False
    import ctypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    try:
        user32.AllowSetForegroundWindow(-1)          # ASFW_ANY
    except Exception:  # noqa: BLE001
        pass
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)                   # SW_RESTORE
    user32.BringWindowToTop(hwnd)
    if user32.SetForegroundWindow(hwnd):
        return True
    VK_MENU, KEYEVENTF_KEYUP = 0x12, 0x0002
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    return bool(user32.SetForegroundWindow(hwnd))


def _foreground_window() -> int:
    if sys.platform != "win32":
        return 0
    import ctypes

    return int(ctypes.WinDLL("user32").GetForegroundWindow() or 0)


def _is_minimized(hwnd: int) -> bool:
    if sys.platform != "win32":
        return False
    import ctypes

    return bool(ctypes.WinDLL("user32").IsIconic(hwnd))


def focus_browser(before: list[int], timeout: float = 8.0) -> None:
    """等浏览器把窗口/标签开出来，然后把它提到软件前面。

    `before` 是点开之前就存在的浏览器窗口。分三种情况：
      1. 浏览器自己已经到前台了 → 什么都不做（别去动用户正在看的窗口）
      2. 冒出新的浏览器窗口（首次启动 / 开了新窗口）→ 提新的那个
      3. 还是原来的窗口（只是加了个标签）→ 等一小会儿确认它没自己跳上来，再提它
    浏览器冷启动可能要好几秒，所以给到 8 秒。
    """
    if sys.platform != "win32":
        return
    known = set(before)
    started = time.time()
    deadline = started + timeout
    while time.time() < deadline:
        time.sleep(0.25)
        now = browser_windows()
        if not now:
            continue                      # 浏览器还在启动，继续等
        if _foreground_window() in now:
            return                        # 已经在前面了，收工
        fresh = [h for h in now if h not in known]
        if fresh:
            raise_window(fresh[0])         # 枚举按 Z 序，最新的窗口排最前
            return
        if time.time() - started >= 1.5:   # 老窗口只是加了个标签：提它
            target = next((h for h in now if not _is_minimized(h)), now[0])
            raise_window(target)
            return


def open_in_browser(url: str) -> None:
    """打开网址，并确保浏览器窗口显示在软件前面。"""
    before = browser_windows()          # 必须在打开之前拍快照
    webbrowser.open(url)
    threading.Thread(target=focus_browser, args=(before,), daemon=True).start()


# ---------------------------------------------------------------- HTTP 服务


class Handler(SimpleHTTPRequestHandler):
    catalog: Catalog
    userdata: UserData

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, *args):  # 保持控制台安静
        pass

    # ---- 工具

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    # ---- 路由
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/catalog":
            return self._json({"items": self.catalog.items, "facets": self.catalog.facets()})
        if parsed.path == "/api/userdata":
            return self._json(self.userdata.data)
        if parsed.path == "/api/ai":
            return self._json(provider_status())
        if parsed.path == "/api/ping":
            return self._json({"ok": True, "items": len(self.catalog.items),
                               "mobile": MOBILE_SITE})
        if parsed.path == "/api/ai/local":
            return self._json({"ok": True, "local": ollama_status(),
                               "suggest": LOCAL_MODELS,
                               "install": install_progress(),
                               "sources": [name for name, _ in OLLAMA_SOURCES]})
        if parsed.path == "/api/ai/pull":
            return self._json({"ok": True, "progress": pull_progress()})
        if parsed.path == "/api/ai/installer":
            return self._json({"ok": True, "progress": install_progress()})

        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        payload = self._read_json()

        if parsed.path == "/api/search":
            items = search(
                self.catalog,
                str(payload.get("query", "")),
                str(payload.get("campus", "")),
                str(payload.get("audience", "")),
                str(payload.get("purpose", "")),
                str(payload.get("kind", "")),
                str(payload.get("platform", "")),
                int(payload.get("limit", 60)),
            )
            return self._json({"items": items})

        if parsed.path == "/api/favorite":
            favs = self.userdata.toggle_favorite(str(payload.get("id", "")), payload.get("on"))
            return self._json({"favorites": favs})

        if parsed.path == "/api/touch":
            recent = self.userdata.touch(str(payload.get("id", "")))
            return self._json({"recent": recent})

        if parsed.path == "/api/history":
            if payload.get("clear"):
                return self._json({"history": self.userdata.clear_search()})
            history = self.userdata.record_search(str(payload.get("query", "")))
            return self._json({"history": history})

        # 首次打开时问一次的"校区 + 身份"（取代原来的两排筛选）
        if parsed.path == "/api/profile":
            return self._json({"ok": True, "profile": self.userdata.set_profile(payload)})

        # 界面上的"AI 设置"：本机模型（不需要 Key）
        if parsed.path == "/api/ai/local":
            if payload.get("model"):
                res = use_ollama_model(str(payload["model"]))
                res["status"] = provider_status()
                return self._json(res)
            return self._json({"ok": True, "local": ollama_status(),
                               "suggest": LOCAL_MODELS, "install": install_progress()})

        if parsed.path == "/api/ai/pull":
            return self._json(start_model_pull(str(payload.get("model", ""))))

        if parsed.path == "/api/ai/installer":
            return self._json(start_ollama_installer(str(payload.get("url", ""))))

        if parsed.path == "/api/ai/serve":
            res = start_ollama_service()
            res["local"] = ollama_status()
            res["status"] = provider_status()
            return self._json(res)

        if parsed.path == "/api/open":
            url = str(payload.get("url", "")).strip()
            if not url and payload.get("id"):
                item = self.catalog.by_id.get(str(payload["id"]))
                url = item.get("url", "") if item else ""
            # 白名单：收录目录里的网址，外加"首页那条手机端网址"（自己部署的站点）。
            # 这样即使有人伪造请求，本地服务也不会被当成打开任意地址的跳板。
            if not url or not (noscheme(url) in self.catalog.allowed_keys
                               or noscheme(url) == noscheme(MOBILE_SITE)):
                return self._json({"ok": False, "error": "该地址不在收录目录中，已拒绝打开"}, 400)
            try:
                open_in_browser(url)
            except Exception as exc:  # noqa: BLE001
                return self._json({"ok": False, "error": str(exc)}, 500)
            return self._json({"ok": True, "opened": url})

        if parsed.path == "/api/ask":
            question = str(payload.get("question", "")).strip()
            if not question:
                return self._json({"ok": False, "error": "问题为空"}, 400)
            inferred = infer_filters(question)
            candidates = ai_candidates(self.catalog, question, inferred, limit=12)
            result = llm_ask(question, candidates, payload.get("history") or [], inferred)
            if not result.get("ok"):
                fallback = local_answer(question, candidates, str(result.get("reason", "")))
                fallback["note"] = result.get("reason", "")
                return self._json(fallback)
            if not result.get("items"):
                result["items"] = [it["id"] for it in candidates[:3]]
            return self._json(result)

        return self._json({"ok": False, "error": "unknown endpoint"}, 404)


# ---------------------------------------------------------------- 启动


def free_port(preferred: int = 8765) -> tuple[int, bool]:
    """返回 (端口, 是否用了首选端口)。优先用首选端口，被占用时顺延，最后才随机。"""
    for port in [preferred] + [preferred + i for i in range(1, 10)] + [0]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                chosen = sock.getsockname()[1]
                return chosen, chosen == preferred
            except OSError:
                continue
    raise RuntimeError("无法分配端口")


def find_edge() -> str | None:
    candidates = [
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def existing_instance() -> str | None:
    """端口文件里那个实例还活着吗？活着就返回它的地址，用于单实例复用。"""
    try:
        port = int(PORT_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    probe = f"http://127.0.0.1:{port}/api/ping"
    try:
        with urllib.request.urlopen(probe, timeout=1.5) as resp:
            if resp.status == 200 and b'"ok"' in resp.read(120):
                return f"http://127.0.0.1:{port}/index.html"
    except Exception:  # noqa: BLE001 - 探测失败就当没有实例
        return None
    return None


def open_window(url: str, args) -> None:
    """用 Edge 的 --app 模式开一个无边框窗口（找不到 Edge 就退回默认浏览器）。"""
    if args.browser:
        webbrowser.open(url)
        return
    edge = find_edge()
    if not edge:
        webbrowser.open(url)
        return
    argv = [
        edge, f"--app={url}", "--window-size=1280,860",
        "--user-data-dir=" + str(APP_DIR / ".edge-profile"),
    ]
    if args.debug_port:
        argv.append(f"--remote-debugging-port={args.debug_port}")
    subprocess.Popen(argv)


def main() -> None:
    parser = argparse.ArgumentParser(description="厦大统一门户")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--browser", action="store_true", help="用默认浏览器打开")
    parser.add_argument("--no-window", action="store_true", help="只启动服务，不打开窗口")
    parser.add_argument("--debug-port", type=int, default=0,
                        help="调试用：让窗口进程开放 DevTools 端口（默认关闭）")
    parser.add_argument("--new", action="store_true",
                        help="即使已有实例在运行，也强制再起一个（默认复用已有实例）")
    parser.add_argument("--mobile-url", default="",
                        help="覆盖首页显示的手机端网址（默认用内置的部署地址）")
    args = parser.parse_args()

    if args.mobile_url.strip():
        global MOBILE_SITE
        MOBILE_SITE = args.mobile_url.strip()

    if not DATA_FILE.exists():
        print("缺少数据文件 data/portal.json，请先运行：python tools/build_data.py")
        sys.exit(1)

    # 单实例：已经有健康实例在跑就复用它，避免"两个实例各占一个端口、
    # 其中一个退出后旧窗口刷新只看到一片空白"这种困惑（用户反馈过的现象）。
    if not args.new and not args.no_window:
        alive = existing_instance()
        if alive:
            print(f"检测到已在运行的实例，直接打开它：{alive}", flush=True)
            open_window(alive, args)
            return

    Handler.catalog = Catalog()
    Handler.userdata = UserData()

    port, got_preferred = free_port(args.port)
    if not got_preferred:
        print(f"提示：端口 {args.port} 已被占用，改用 {port}", flush=True)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/index.html"
    try:
        PORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        PORT_FILE.write_text(str(port), encoding="utf-8")
    except OSError:
        pass  # 端口文件写不了不影响运行

    threading.Thread(target=server.serve_forever, daemon=True).start()
    chain = provider_chain()
    first = chain[0]
    if first == "local":
        key_state = "纯本地检索（没有可用的大模型 Key）"
    else:
        key_state = f"{PROVIDERS[first]['label']}（降级链：{' → '.join(PROVIDERS[c]['label'] if c in PROVIDERS else '本地检索' for c in chain)}）"
    print(f"厦大统一门户已启动：{url}", flush=True)
    print(f"收录条目：{len(Handler.catalog.items)} 条 | AI 引擎：{key_state}", flush=True)

    if args.no_window:
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return

    if args.browser:
        webbrowser.open(url)
    else:
        open_window(url, args)

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
