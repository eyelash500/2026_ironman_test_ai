# 受測物快照

| 檔案 | 角色 | 說明 |
|---|---|---|
| `進階退休規劃試算.html` | **受測物** | 2025-09-19 製作，真實上線一年。四個缺陷都在這裡 |
| `退休金缺口計算機-iron.html` | **對照組** | 2025-09-09 製作，2025 系列文章 Day 6-11 的專案。四個缺陷一個都沒有 |

兩份皆為 2026-09-03 的凍結快照。線上版預計 Day 30 修復部署，屆時會與此處不同。

## 經實測行號（受測物，2026-09-03 逐條 grep 覆核）

| 行 | 內容 | 關聯 |
|---|---|---|
| 215 | `parseNumber`，`parseFloat(...) \|\| 0` | 缺陷 D |
| 293 | `retirementYears = lifeExpectancy - retirementAge`（純減法，無防護） | 缺陷 B |
| 297 | `monthlyPreReturn = preRetirementReturn / 12` | 模型假設偏差 |
| 306 | 目標金額迴圈 `for (let i = 1; i <= retirementYears; i++)` | 缺陷 A、B |
| 321-322 | 期末折現 | 缺陷 A |
| 327 | 大筆支出年齡 `parseInt` | 缺陷 D |
| 329 | `if (age >= retirementAge)`（僅檢查下界） | 缺陷 C、D |
| 349 | 圖表提領迴圈 | 缺陷 C |
| 367 | 大筆支出年份比對 `=== age` | 缺陷 C |
| 372 | 期初扣款（先扣後滾） | 缺陷 A |
| 374 | `assetData.push(Math.max(0, remainingFund))` | 缺陷 A' |

⚠️ 引用行號前請重新 grep 一次。這張表本身曾有一條偏一行（`/12` 原記 298）。
