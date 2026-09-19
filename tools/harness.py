"""變異執行引擎：注入缺陷、隔離執行、依回傳碼判定。

三件不能退讓的事
--------------
1. **注入靠檔案置換，不靠環境變數。** 在受測原始碼裡塞
   `if os.getenv("ACTIVE_MUTANT") == ...` 等於把變異體當分支埋進
   一份已經驗收過的資產。本檔每次鏡射整棵樹到暫存目錄，改副本，用完即刪。

   **鏡射整棵樹，不是只複製單一檔案。** `tests/test_checklist.py` 開頭寫著
   `sys.path.insert(0, str(ROOT / "shadow"))`——插在搜尋路徑最前面，
   指向本機真正的 `shadow/`。若只把變異後的單檔丟進暫存目錄再靠 `PYTHONPATH` 接，
   優先序搶不過它，測試會 import 到未變異的原檔，**每個變異體都回報 SURVIVED、
   分數恆為 0%，而且不會報錯**。`--naive` 保留了那個錯誤做法，
   校準時可以親眼看它壞給你看。

2. **片段必須唯一。** `replace(..., 1)` 只換第一處，目標片段出現兩次就會
   默默改錯地方；出現零次代表變異定義過期。兩種都直接中止。

3. **判定看回傳碼，不是「非 0 即殺」。** pytest 的回傳碼有精確語意：
   `0` 全過 → SURVIVED、`1` 有測試失敗 → KILLED、
   `2/3/4/5`（中斷、內部錯誤、用法錯、沒收集到測試）→ ERROR，不入分數。
   語法錯的變異體回傳 2，用「非 0 即殺」會把它算成擊殺——
   **那不是測試套件的功勞，是編譯器的功勞。**

誰驗收這支
---------
`tools/calibration_mutants.py` 的五條校準變異體，答案人手寫、跑之前定。
必死組、必活組、必錯組全部命中預期，本檔才准去跑正式的領域變異體。

    python3 tools/harness.py --calibrate
    python3 tools/harness.py --calibrate --naive      # 看錯誤做法怎麼壞
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum


class Verdict(Enum):
    KILLED = "killed"       # returncode 1：有測試失敗
    SURVIVED = "survived"   # returncode 0：全過
    TIMEOUT = "timeout"     # 逾時：視為 killed，但另記
    ERROR = "error"         # returncode 2/3/4/5：不入分數


@dataclass(frozen=True)
class Mutant:
    id: str
    original: str       # 受測原始碼中必須「剛好出現一次」的片段
    mutated: str        # 置換後的片段
    simulates: str      # 模擬哪一種真實錯法


def apply_mutant(project_root: str, rel_source: str, m: Mutant, workdir: str,
                 naive: bool = False) -> str:
    """把專案鏡射到 workdir 並在副本上置換。回傳副本的根目錄。

    `naive=True` 時只複製單一檔案（示範失敗做法）。
    """
    src = open(os.path.join(project_root, rel_source), encoding="utf-8").read()
    hits = src.count(m.original)
    if hits != 1:
        raise ValueError(f"[{m.id}] 目標片段在原始碼出現 {hits} 次，必須剛好 1 次")
    mutated_src = src.replace(m.original, m.mutated)

    root_copy = os.path.join(workdir, "proj")
    if naive:
        # 失敗做法：只放變異後的單檔，其餘靠本機路徑
        target = os.path.join(root_copy, rel_source)
        os.makedirs(os.path.dirname(target), exist_ok=True)
    else:
        shutil.copytree(project_root, root_copy, symlinks=True,
                        ignore_dangling_symlinks=True,
                        ignore=shutil.ignore_patterns(
                            ".git", "__pycache__", "*.pyc",
                            "venv*", ".venv*", "*.egg-info", ".pytest_cache"))
        target = os.path.join(root_copy, rel_source)
    open(target, "w", encoding="utf-8").write(mutated_src)
    return root_copy


def run_tests(root_copy: str, rel_tests: str, project_root: str,
              timeout_sec: float = 30.0, naive: bool = False) -> Verdict:
    """在副本裡執行測試，讓測試檔自己的 ROOT 解析到副本。"""
    cwd = root_copy
    env = os.environ.copy()
    if naive:
        # 失敗做法：測試檔留在原專案，只用 PYTHONPATH 指向副本
        cwd = project_root
        env["PYTHONPATH"] = f"{root_copy}:{env.get('PYTHONPATH', '')}".rstrip(":")

    cmd = [sys.executable, "-m", "pytest", rel_tests, "-q", "-p", "no:cacheprovider"]
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout_sec,
                              capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        return Verdict.TIMEOUT
    return {0: Verdict.SURVIVED, 1: Verdict.KILLED}.get(proc.returncode, Verdict.ERROR)


def evaluate(project_root: str, rel_source: str, rel_tests: str,
             mutants, equivalent_ids=None, naive: bool = False) -> dict:
    equivalent_ids = set(equivalent_ids or ())
    results: dict[str, Verdict] = {}
    for m in mutants:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                root_copy = apply_mutant(project_root, rel_source, m, tmp, naive)
                verdict = run_tests(root_copy, rel_tests, project_root, naive=naive)
            except Exception:                                   # noqa: BLE001
                verdict = Verdict.ERROR
            results[m.id] = verdict

    scored = [i for i, v in results.items()
              if v is not Verdict.ERROR and i not in equivalent_ids]
    killed = [i for i in scored
              if results[i] in (Verdict.KILLED, Verdict.TIMEOUT)]
    return {
        "results": results,
        "killed": len(killed),
        "scored": len(scored),
        "error": sum(1 for v in results.values() if v is Verdict.ERROR),
        "equivalent": len(equivalent_ids),
        "score": (len(killed) / len(scored) * 100) if scored else None,
    }


def _assert_baseline(project_root: str, rel_tests: str) -> None:
    """跑變異之前先證明「跑得到測試，而且未變異時是全綠的」。

    沒有這一條，一個沒裝 pytest 的環境會讓五條校準全部回 ERROR——
    必錯組因此「碰巧命中預期」，在報表上顯示為打勾。
    Day 14 的 `_assert_baseline()` 與 Day 17 的 `_assert_all_ran()` 同源：
    工具在什麼都沒做的時候必須閉嘴，而不是報出一個看起來合理的結論。
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", rel_tests, "-q", "-p", "no:cacheprovider"],
        cwd=project_root, capture_output=True, text=True,
    )
    if proc.returncode == 0:
        return
    if proc.returncode in (4, 5) or "No module named pytest" in proc.stderr:
        raise SystemExit(
            "中止：這個環境跑不起 pytest（回傳碼 "
            f"{proc.returncode}）。校準的每一條都會變成 ERROR，"
            "必錯組會因此假通過。"
        )
    raise SystemExit(
        f"中止：未變異的 {rel_tests} 就不是全綠（回傳碼 {proc.returncode}）。"
        "基準線紅的，變異結果沒有意義。"
    )


def calibrate(project_root: str, naive: bool = False) -> int:
    """跑校準考卷。全部命中預期回傳 0，否則回傳 1 並逐條列出。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from calibration_mutants import CALIBRATION, REL_SOURCE, REL_TESTS

    _assert_baseline(project_root, REL_TESTS)
    print(f"基準線：未變異時 {REL_TESTS} 全綠")
    print(f"校準模式{'（--naive：刻意使用失敗做法）' if naive else ''}")
    problems: list[str] = []
    for group, mutants, expected in CALIBRATION:
        out = evaluate(project_root, REL_SOURCE, REL_TESTS, mutants, naive=naive)
        for m in mutants:
            got = out["results"][m.id].value
            mark = "✓" if got == expected else "✗"
            print(f"  {mark} {group}　{m.id}　預期 {expected:<8} 實得 {got:<8} {m.simulates}")
            if got != expected:
                problems.append(f"{m.id}：預期 {expected}，實得 {got}")

    if problems:
        print(f"\n校準未通過（{len(problems)} 條不符），harness 不列裝：")
        for p in problems:
            print("  -", p)
        return 1
    print("\n五條全部命中預期，harness 列裝。")
    return 0


def run_domain(project_root: str) -> int:
    """正式一輪：14 個領域變異體打在 calc_fixed 上，由 golden v2 套件應戰。

    基底與套件的配對只有一種可能：領域變異體改的是 `shadow/calc_fixed.py`，
    而 repo 裡唯一 import `calc_fixed` 的套件是 `tests/test_golden_v2.py`。
    `tests/test_characterization.py` 對的是 legacy `calc.py`，這些變異體打不到它。
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from domain_mutants import DOMAIN_MUTANTS, EVIDENCE, REL_SOURCE, audit

    if audit() != 0:
        raise SystemExit("中止：目錄自檢未通過，不注入")

    rel_tests = "tests/test_golden_v2.py"
    _assert_baseline(project_root, rel_tests)
    print(f"基準線：未變異時 {rel_tests} 全綠\n")

    out = evaluate(project_root, REL_SOURCE, rel_tests, DOMAIN_MUTANTS)
    for m in DOMAIN_MUTANTS:
        v = out["results"][m.id].value
        mark = {"killed": "✓ 殺掉", "survived": "✗ 存活",
                "timeout": "✓ 逾時", "error": "! 無效"}[v]
        print(f"  {mark}　{m.id}　{EVIDENCE[m.id]}")

    score = out["score"]
    print(f"\n殺掉 {out['killed']} / 計分 {out['scored']}"
          f"（總數 {len(DOMAIN_MUTANTS)}、ERROR {out['error']}、等價 {out['equivalent']}）")
    print(f"變異分數 = {score:.1f}%" if score is not None else "變異分數：無法計算")
    print("\n存活的每一個都要人工驗屍：真漏洞，還是等價變異體？工具不猜。")
    return 0


def main(argv: list[str]) -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if "--calibrate" in argv:
        return calibrate(root, naive="--naive" in argv)
    if "--domain" in argv:
        return run_domain(root)
    raise SystemExit("用法：harness.py --calibrate [--naive] ｜ --domain")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
