#!/usr/bin/env bash
# Day 30-B：修復版上線前的驗收。四件事同時成立才准部署。
#
#   一、舊快照紅在預期處   tests/test_characterization.py 對 calc_fixed 跑，應該紅
#   二、新規格測試綠       tests/test_golden_v2.py 全綠
#   三、關係在新舊兩版符合預期   tests/test_metamorphic.py：fixed 全綠，legacy 紅在 MR-04
#   四、JS 移植與 Python 逐位元對齊   tools/diff_fixed.py（沙箱已跑，此處重跑存證）
# 外加：M14 那條測試在 calc_fixed 綠、注入 M14 紅
#
#     bash generated/2026-09-30-fix-release/verify.sh
#
# 需在 repo 根目錄、已 source venv 的情況下執行。

set -u
cd "$(dirname "$0")/../.." || exit 1
OUT="generated/2026-09-30-fix-release/results"
mkdir -p "$OUT"

echo "環境：$(python3 -V)、pytest $(python3 -m pytest --version 2>&1 | head -1)、node $(node --version)"

# ── 一、舊快照對修復版：把 characterization 的 import 暫時指到 calc_fixed ──
{
  echo "# 一、舊快照（Day 7 characterization，鎖 legacy 行為）對 calc_fixed"
  echo "# 預期：紅。紅的每一條都要能對應到第一幕的某個缺陷或 PRD v1.x 的某條裁決"
  sed 's/^from calc import /from calc_fixed import /' tests/test_characterization.py > tests/_char_on_fixed.py
  python3 -m pytest tests/_char_on_fixed.py -q -p no:cacheprovider 2>&1 | tail -30
  rm -f tests/_char_on_fixed.py
} | tee "$OUT/1-old-snapshot-on-fixed.txt"

# ── 二、新規格測試 ──
{
  echo "# 二、golden v2（PRD v1.2）對 calc_fixed，預期全綠"
  python3 -m pytest tests/test_golden_v2.py -q -p no:cacheprovider 2>&1 | tail -3
} | tee "$OUT/2-golden-v2.txt"

# ── 三、蛻變關係在新舊兩版 ──
{
  echo "# 三、四條關係：fixed 全綠；legacy 只有 MR-04 紅（Day 25 已實測）"
  python3 -m pytest tests/test_metamorphic.py -q -p no:cacheprovider 2>&1 | tail -8
} | tee "$OUT/3-metamorphic-both.txt"

# ── 四、JS 移植 ──
{
  echo "# 四、oracle/calc_fixed.js 對 shadow/calc_fixed.py，505 組（含 5 組違規），預期 0 不符"
  python3 tools/diff_fixed.py
} | tee "$OUT/4-diff-js-py.txt"

# ── M14 ──
{
  echo "# M14：補上非零收入的關係。calc_fixed 綠；逐條跑十四個變異體，M14 必須被殺掉"
  python3 -m pytest tests/test_prd10_income_indexed.py -q -p no:cacheprovider 2>&1 | tail -3
  echo "---"
  python3 tools/mr_audit_batch.py tests/test_prd10_income_indexed.py 2>&1 | grep -v "^KAT"
} | tee "$OUT/5-m14.txt"

echo
echo "五份輸出在 $OUT/。四件事都成立、M14 死了，才准部署 v2。"
