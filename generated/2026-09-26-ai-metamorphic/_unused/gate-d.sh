#!/usr/bin/env bash
# Day 26 第四道關：逐條關係的變異體驗收。
#
# 為什麼單獨一支：143 條關係 × 14 個變異體 ≈ 兩千次 pytest，
# 跟前三關綁在一起會讓「快速驗收」變成半小時的事。
# 這支的產物主要服務 Day 27（「那些關係有沒有用」），
# Day 26 的主指標是分類，不是分數。
#
#     bash generated/2026-09-26-ai-metamorphic/gate-d.sh
#
# 需在 repo 根目錄、已 source venv 的情況下執行。可以放著跑。

set -u
cd "$(dirname "$0")/../.." || exit 1
D="generated/2026-09-26-ai-metamorphic"
OUT="$D/results"
mkdir -p "$OUT"

{
  echo "# 關 D：tools/mr_audit_batch.py，逐條關係單獨跑十四個領域變異體"
  echo "# 判定沿用 Day 18：回傳碼 1 殺掉、0 存活、其餘無效"
  echo "# 這把尺只能證實，不能證偽（Day 25 的更正）"
  echo "# 開始 $(date '+%F %T')"
  for f in "$D"/run-?-MR-0?.txt; do
    echo "########## $(basename "$f") ##########"
    python3 tools/mr_audit_batch.py "$f" 2>&1 | grep -v "^KAT"
  done
  echo "# 結束 $(date '+%F %T')"
} | tee "$OUT/gate-d.txt"
