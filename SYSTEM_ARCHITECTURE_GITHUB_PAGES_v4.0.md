# 5人制抽籤互助會網頁版系統架構 v4.0

## 架構
GitHub Repository → GitHub Pages → web/index.html → web/app.js → Browser Simulation → localStorage / JSON / Canvas。

## Python 移植
原 app_v3_fixed.py 的試算規則移至 JavaScript；Python HTTPServer 與 /api/simulate_v3 不再是 Web Pages 執行必要條件。

## 資料安全
GitHub 僅存程式碼；真實會員、銀行及繳款資料不得 commit。

## 後續
若需登入、多人共同編輯、中央資料與稽核，再導入 GAS + Google Sheets 或資料庫。