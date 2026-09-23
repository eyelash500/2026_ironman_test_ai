"""雙向洩漏掃描：不該出現的有沒有出現，該出現的有沒有漏掉。

為什麼要雙向
----------
Day 15 第一輪只掃「不該有的在不在」，結果漏掉的是**該有而被刪掉的**——
貼上檔少了函式簽名，模型只好自己取名字，整份產物的進入點對不上，作廢重跑。
單向掃描擋得住洩題，擋不住殘缺。所以本檔兩邊都掃，任一邊不過就中止。

工具不做裁決
----------
命中一個關鍵詞不等於作廢。Day 21 掃出 `amounts` 與 `PRD-xx` 兩項，
人工判為可接受並寫進 manifest——`amounts` 是受測原始碼的區域變數，
看不到它就不知道校驗涵蓋哪些欄位，那正是當天要量的東西。
所以本檔的規則是：**命中就印出來，連同上下文**；
要讓它過，得把該詞明文寫進 `accept`，等於在 manifest 上簽名。
沒簽名的命中一律回傳 1。

    python3 tools/leak_scan.py <設定檔.py>
    python3 tools/leak_scan.py --self-test
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys


def _norm(text: str) -> str:
    """英數字轉小寫比對；中文不受影響。"""
    return text.lower()


def find_hits(text: str, terms) -> dict[str, list[tuple[int, str]]]:
    """回傳 {關鍵詞: [(行號, 該行內容), ...]}，只收真的命中的詞。"""
    lines = text.split("\n")
    hits: dict[str, list[tuple[int, str]]] = {}
    for term in terms:
        t = _norm(term)
        found = [(i + 1, ln.strip()) for i, ln in enumerate(lines) if t in _norm(ln)]
        if found:
            hits[term] = found
    return hits


def find_missing(text: str, terms) -> list[str]:
    """回傳 must_have 裡沒出現的詞。"""
    body = _norm(text)
    return [t for t in terms if _norm(t) not in body]


def scan(text: str, must_not, must_have, accept=()) -> dict:
    accept = set(accept)
    hits = find_hits(text, must_not)
    return {
        "hits": hits,
        "unsigned": {k: v for k, v in hits.items() if k not in accept},
        "accepted": {k: v for k, v in hits.items() if k in accept},
        "missing": find_missing(text, must_have),
    }


def report(name: str, out: dict) -> int:
    print(f"\n── {name} ──")
    print(f"must_not：{len(out['hits'])} 項命中"
          f"（已簽名 {len(out['accepted'])}、未簽名 {len(out['unsigned'])}）")
    for term, places in out["accepted"].items():
        print(f"  ○ {term}（已簽名）　第 {', '.join(str(n) for n, _ in places)} 行")
    for term, places in out["unsigned"].items():
        print(f"  ✗ {term}　未簽名")
        for n, line in places[:3]:
            print(f"      {n}: {line[:70]}")
    missing = out["missing"]
    print(f"must_have：{len(missing)} 項缺漏")
    for term in missing:
        print(f"  ✗ 缺 {term}")
    ok = not out["unsigned"] and not missing
    print("判定：通過" if ok else "判定：不通過")
    return 0 if ok else 1


def run_config(path: str) -> int:
    spec = importlib.util.spec_from_file_location("leak_cfg", path)
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)

    base = os.path.dirname(os.path.abspath(path))
    rc = 0
    for name, rel in cfg.TARGETS.items():
        text = open(os.path.join(base, rel), encoding="utf-8").read()
        out = scan(text, cfg.MUST_NOT, cfg.MUST_HAVE.get(name, ()), cfg.ACCEPT.get(name, ()))
        rc |= report(f"{name}（{rel}）", out)
    print("\n全部通過，可以貼。" if rc == 0 else "\n有項目不通過，不准貼。")
    return rc


def self_test() -> int:
    """KAT：人手寫、答案確鑿，用來驗收掃描器本身。"""
    text = "class Params:\n    x = 1  # 這裡有個缺陷\ndef calculate(p): ...\n"

    a = scan(text, ["缺陷"], ["class Params"])
    assert a["unsigned"] and not a["missing"], "該抓到的沒抓到"

    b = scan(text, ["缺陷"], ["class Params"], accept=["缺陷"])
    assert not b["unsigned"] and b["accepted"], "簽名之後不該再算未簽名"

    c = scan(text, ["變異"], ["def calculate", "class Result"])
    assert not c["hits"] and c["missing"] == ["class Result"], "缺漏偵測失準"

    d = scan("MUTATION SCORE", ["mutation"], [])
    assert d["unsigned"], "英數字比對應忽略大小寫"

    e = scan("完全乾淨的一句話", ["變異"], [])
    assert not e["hits"] and not e["missing"], "乾淨輸入不該有任何告警"

    print("五條 KAT 全部命中預期，掃描器可用。")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    if len(argv) < 2:
        raise SystemExit("用法：leak_scan.py <設定檔.py>　｜　leak_scan.py --self-test")
    if self_test() != 0:
        raise SystemExit("中止：掃描器自檢未過")
    return run_config(argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
