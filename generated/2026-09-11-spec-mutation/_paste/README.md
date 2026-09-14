# 這個資料夾是衍生物，不是實驗輸入

每個 `paste-*.txt` = `../prompt.md` 的「提示詞本體」+ 對應的 `../input-prd-mut-*.md`，
用底下這段程式串起來的，沒有加任何一個字：

    body = prompt.md 裡「## 提示詞本體」到「（此處貼上」之間那段
    paste-<arm>.txt = body + "\n\n" + input-prd-mut-<arm>.md

存在的理由只有一個：手動跑三十次的時候少一個出錯的機會。
**實驗的正本仍是 `prompt.md` 與 `input-prd-mut-*.md`。**
若兩者有出入，以正本為準。
