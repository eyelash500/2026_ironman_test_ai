"""Day 26 貼上檔的洩漏掃描設定。跑之前定。

    python3 tools/leak_scan.py generated/2026-09-26-ai-metamorphic/leak_config.py
"""

TARGETS = {"MR": "_paste/paste-mr.txt"}

MUST_NOT = [
    # 實驗本身
    "變異", "mutant", "mutation", "harness", "存活", "殺掉", "分數",
    "廢話", "恆真", "實驗", "生成", "temperature",
    # 我自己寫的四條關係——一個字都不能透露，否則量到的是抄寫
    "MR-01", "MR-02", "MR-03", "MR-04", "齊次", "自我一致", "單調",
    "支出配置", "月支出與固定年支出", "資金剛好",
    # 受測物來歷
    "缺陷", "defect", "bug", "修復", "legacy", "calc.py", "影子模型", "受測物",
    # 既有量測
    "覆蓋率", "coverage", "盲區", "忠實性", "真空", "golden", "閘門",
    # 系列脈絡
    "鐵人", "ithome", "本系列", "Day ", "v1.0", "v1.1",
    # 規格條款裡的禁止句（Day 11 認定的效度威脅，逐個簽名）
    "禁止", "Math.max", "不得",
]

MUST_HAVE = [
    "class LumpSum", "class Params", "class Result",
    "def calculate(p: Params) -> Result",
    "tests/test_ai_mr.py", "pytest.skip",
    "不得寫死任何期望值",
    "多次執行之間的關係",
    'sys.path.insert(0, str(ROOT / "shadow"))',
    "from calc_fixed import LumpSum, Params, Result, calculate",
] + [f"PRD-{n:02d}" for n in range(1, 13)]

MUST_HAVE = {"MR": MUST_HAVE}

ACCEPT = {
    "MR": [
        # 硬性約束的措辭，限制產出形式，不透露計算行為
        "不得",
        # PRD-03／04／12 的禁止句，Day 11 已認定為效度威脅，沿用 Day 22 的判定
        "禁止", "Math.max",
        # 示範例子改用 sort()，與本題領域無關——
        # 原本寫的兩個例子剛好就是作者的 MR-01 與 MR-02，
        # 那樣量到的會是「它會不會照抄」，不是「它想不想得到」。
    ],
}
