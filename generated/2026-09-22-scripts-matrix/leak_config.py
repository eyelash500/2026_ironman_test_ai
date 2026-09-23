"""Day 22 兩份貼上檔的洩漏掃描設定。跑之前定，跑完不改。

    python3 tools/leak_scan.py generated/2026-09-22-scripts-matrix/leak_config.py
"""

TARGETS = {
    "L1": "_paste/paste-l1.txt",
    "PRD": "_paste/paste-prd.txt",
}

# 不該出現的。分四類：實驗本身、受測物來歷、既有量測、系列脈絡。
MUST_NOT = [
    # 實驗本身
    "變異", "mutant", "mutation", "harness", "存活", "殺掉", "分數",
    "對比矩陣", "實驗", "生成", "temperature",
    # 受測物來歷（知道它有缺陷，就會照著缺陷寫測試）
    "缺陷", "defect", "bug", "修復", "修正版", "驗屍",
    "legacy", "calc.py", "影子模型", "characterization", "受測物", "上線",
    # 既有量測（知道別人量過什麼，就會往那裡寫）
    "覆蓋率", "coverage", "盲區", "忠實性", "真空", "assert_inspector",
    "golden", "閘門",
    # 系列脈絡
    "鐵人", "ithome", "本系列", "Day ", "v1.0", "v1.1",
    # 規格條款裡的禁止句（Day 11 已認定的效度威脅，必須逐個簽名）
    "禁止", "Math.max", "不得",
]

# 該出現的。少一項，產物就會對不上進入點或跑不起來。
_SHARED = [
    "class LumpSum", "class Params", "class Result",
    "def calculate(p: Params) -> Result",
    "tests/test_ai_matrix.py", "pytest.skip",
    "不得修改介面", "逐字使用", "不得詢問",
    "函式本體不提供",
    # 進入點那一段。Day 15 第一輪就是漏了函式簽名，產物取錯名字整批作廢。
    'sys.path.insert(0, str(ROOT / "shadow"))',
    "from calc_fixed import LumpSum, Params, Result, calculate",
]

MUST_HAVE = {
    "L1": _SHARED + ["幫這支退休金試算的計算核心寫 pytest 測試。"],
    "PRD": _SHARED + [f"PRD-{n:02d}" for n in range(1, 13)],
}

# 已簽名的命中：每一條都要有理由，理由進 manifest。
ACCEPT = {
    "L1": [
        # 約束 1、3、5 的措辭。它們限制的是產出形式，不透露任何計算行為。
        "不得",
    ],
    "PRD": [
        "不得",
        # PRD-03「禁止 Math.max(0, ...) 截斷真實餘額」、PRD-04「禁止靜默補零」、
        # PRD-12「不得下限截斷」。這三句是規格本文，刪掉就不是 PRD v1.2 了。
        # 但它們確實是「知道錯在哪之後回頭寫的規格」——Day 11 已認定為效度威脅。
        # 本輪照原樣保留並記在 manifest，不當作洩漏，但也不宣稱 PRD 組是乾淨對照。
        "禁止",
        "Math.max",
    ],
}
