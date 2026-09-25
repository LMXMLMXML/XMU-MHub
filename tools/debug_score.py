import sys
from pathlib import Path

sys.path.insert(0, r"D:\AI\xmu_hub")
import app as portal  # noqa: E402

cat = portal.Catalog()
OUT = Path(r"D:\AI\xmu_hub\data\_debug.txt")
lines = []

queries = sys.argv[1:] or ["报销", "查重", "饭卡"]

for q in queries:
    terms = portal.expand_query(q, portal.tokenize(q))
    rows = []
    for item in cat.items:
        s = portal.score_item(item, terms)
        if s > 0:
            rows.append((s, item))
    rows.sort(key=lambda r: -r[0])
    lines.append(f"\n=== {q} === terms={terms}")
    for s, it in rows[:8]:
        lines.append(f"  {s:6.2f}  {it['name']}  | kw={it.get('keywords', [])[:8]}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("ok")
