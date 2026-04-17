# 81Y3-dashboard LINE Bot

基於 81Y3-dashboard 資料的智能人數查詢 LINE Bot。

## 功能特色

- 🤖 AI 智能查詢：使用 Google Gemini 進行自然語言理解
- 📊 出席趨勢分析：查詢各小區的出席趨勢
- 👥 成員名單查詢：查看各小區成員資訊
- 🏆 排行榜查詢：查看出席積分排名
- 🔄 資料更新：手動更新 RAG 知識庫

## 檔案結構

```
81Y3-dashboard/
├── bot_server.py          # LINE Bot 伺服器
├── dashboard_rag.py        # RAG 系統（處理 81Y3-dashboard 資料）
├── requirements.txt       # Python 依賴
├── Dockerfile            # Docker 配置
├── trend.html            # 出席趨勢資料
├── y1/, y2/, y3/         # 青年區資料
├── hs1/, hs2/, hs3/      # 高中區資料
└── ms1/, ms2/            # 國中區資料
```

## 環境變數設定

需要設定以下環境變數：

```bash
# LINE Bot 設定
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_CHANNEL_SECRET=your_line_channel_secret

# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key

# Google Sheets（可選，用於記錄使用紀錄）
GSPREAD_JSON=your_gspread_json
GOOGLE_SHEET_ID=your_google_sheet_id

# 服務設定
PORT=10000
```

## 本地開發

1. 安裝依賴：
```bash
pip install -r requirements.txt
```

2. 設定環境變數：
```bash
export LINE_CHANNEL_ACCESS_TOKEN=your_token
export LINE_CHANNEL_SECRET=your_secret
export GEMINI_API_KEY=your_key
```

3. 執行服務：
```bash
python bot_server.py
```

## Docker 部署

1. 建構 Docker 映像：
```bash
docker build -t 81y3-bot .
```

2. 執行容器：
```bash
docker run -p 10000:10000 \
  -e LINE_CHANNEL_ACCESS_TOKEN=your_token \
  -e LINE_CHANNEL_SECRET=your_secret \
  -e GEMINI_API_KEY=your_key \
  81y3-bot
```

## Render 部署

1. 連結 GitHub 儲存庫
2. 設定環境變數
3. 部署

## 使用方式

在 LINE 中發送訊息：

```
81人數助理 青年一區有多少人？
81人數助理 誰的出席率最高？
81人數助理 弟兄青職的成員有哪些？
81人數助理 最近幾週主日出席趨勢如何？
81人數助理 幫助
81人數助理 更新
```

## 注意事項

- 確保 `trend.html` 和各小區的 JSON 檔案存在
- Google Gemini API 需要有效的 API Key
- LINE Bot 需要設定 Webhook URL
