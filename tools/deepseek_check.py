"""DeepSeek 调用路径的离线验证：用假响应替代真实网络请求。

真实调用需要 DEEPSEEK_API_KEY，这里通过 monkeypatch 验证：
  1) 请求体构造是否正确（模型、消息、候选上下文）
  2) 回答与 PICK 解析是否正确
  3) HTTP 错误 / 无 Key 时是否安全降级
"""

from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, r"D:\AI\xmu_hub")
import app as portal  # noqa: E402

OUT = Path(r"D:\AI\xmu_hub\data\_deepseek_check.txt")
lines: list[str] = []
cat = portal.Catalog()
question = "我是研究生，成绩在哪里查"
inferred = portal.infer_filters(question)
terms = portal.tokenize(question)
raw = portal.search(cat, question, **inferred, limit=12, floor=4.0)
candidates = [c for c in raw if portal.strong_match(c, terms)]
if len(candidates) < 3:
    candidates = portal.search(cat, question, limit=12)
    candidates = [c for c in candidates if portal.strong_match(c, terms)] or candidates
lines.append(f"问题：{question}")
lines.append(f"推断筛选：{inferred}")
lines.append(f"净化前候选 {len(raw)} 条：" + " | ".join(c["name"] for c in raw))
lines.append(f"净化后候选 {len(candidates)} 条：" + " | ".join(c["name"] for c in candidates))

captured: dict = {}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_urlopen(req, timeout=None):
    captured["url"] = req.full_url
    captured["headers"] = dict(req.headers)
    captured["body"] = json.loads(req.data.decode("utf-8"))
    answer = (
        "推荐「研究生院」和「教务服务平台」：研究生院是学籍与培养归口，教务服务平台可查成绩。\n"
        "PICK: 1,2"
    )
    payload = {"choices": [{"message": {"content": answer}}]}
    return FakeResponse(json.dumps(payload).encode("utf-8"))


real_urlopen = portal.urllib.request.urlopen
portal._ANSWER_CACHE.clear()          # 答案有缓存，测试前先清空，否则用例 2/3 会命中用例 1 的结果

# --- 用例 1：正常返回 ---
os.environ["DEEPSEEK_API_KEY"] = "sk-test-key"
portal.urllib.request.urlopen = fake_urlopen
res = portal.llm_ask(question + "（用例1）", candidates, [])
portal.urllib.request.urlopen = real_urlopen

lines.append("\n[用例1 正常返回]")
lines.append(f"  ok={res.get('ok')} engine={res.get('engine')} model={res.get('model')}")
lines.append(f"  解析出的 PICK 条目：{res.get('items')}")
lines.append(f"  回答正文（已剥离 PICK）：{res.get('answer')!r}")
lines.append(f"  请求 URL：{captured.get('url')}")
lines.append(f"  请求模型：{captured['body'].get('model')}  stream={captured['body'].get('stream')}")
lines.append(f"  消息条数：{len(captured['body'].get('messages', []))}")
lines.append(f"  是否携带 Authorization：{'Authorization' in captured.get('headers', {})}")
ctx = captured["body"]["messages"][-1]["content"]
probe = candidates[0]["name"] if candidates else "（无候选）"
lines.append(f"  候选是否注入上下文：{probe in ctx}（探测名：{probe}）")
lines.append(f"  上下文长度：{len(ctx)} 字符（用于控制 token 成本）")

# --- 用例 2：接口报错 ---
def failing_urlopen(req, timeout=None):
    raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"error":"bad key"}'))


portal.urllib.request.urlopen = failing_urlopen
res2 = portal.llm_ask(question + "（用例2）", candidates, [])
portal.urllib.request.urlopen = real_urlopen
lines.append("\n[用例2 接口 401]")
lines.append(f"  ok={res2.get('ok')} reason={res2.get('reason')}")
fallback = portal.local_answer(question, candidates, str(res2.get("reason", "")))
lines.append(f"  降级回答：{fallback['answer'][:90]}…")
lines.append(f"  降级 engine={fallback['engine']}，仍返回 {len(fallback['items'])} 个推荐")

# --- 用例 3：未配置 Key ---
os.environ.pop("DEEPSEEK_API_KEY", None)
portal._ANSWER_CACHE.clear()
res3 = portal.llm_ask(question + "（用例3）", candidates, [])
lines.append("\n[用例3 未配置 Key]")
lines.append(f"  ok={res3.get('ok')} reason={res3.get('reason')}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("written")
