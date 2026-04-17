FROM python:3.11-slim

WORKDIR /app

# 複製依賴並安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製程式碼
COPY . .

# 預設 Port 10000
EXPOSE 10000

# 使用 gunicorn 啟動
CMD ["gunicorn", "bot_server:app", "--bind", "0.0.0.0:10000", "--workers", "1"]
