"""
81Y3-dashboard LINE Bot 伺服器
基於 81Y3-dashboard 資料的智能人數查詢助理
"""

import os
import csv
import json
import logging
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 導入 81Y3-dashboard RAG 系統
from dashboard_rag import update_rag_context, generate_response

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- 配置 ---
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 路徑設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_LOG_FILE = os.path.join(BASE_DIR, "users_log.csv")


def get_sheet_conn():
    """建立 Google Sheets 連線"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_json = os.environ.get("GSPREAD_JSON")
        if not creds_json: 
            return None
        
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(os.environ.get("GOOGLE_SHEET_ID"))
    except Exception as e:
        print(f"❌ Google Sheet 連線失敗: {e}")
        return None


def record_interaction(group_id, group_name, user_id, user_name, message):
    """
    處理兩種邏輯：
    1. Users 分頁：紀錄『誰』用過（不重疊，更新最後互動時間）
    2. Logs 分頁：紀錄『訊息流水帳』（每一則都記）
    """
    try:
        sheet = get_sheet_conn()
        if not sheet: 
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # --- A. 更新 Logs (流水帳) ---
        log_ws = sheet.worksheet("Logs")
        # 格式：時間 | 群組ID | 群組名稱 | 使用者ID | 使用者名稱 | 訊息內容
        log_ws.append_row([now, group_id, group_name, user_id, user_name, message])

        # --- B. 更新 Users (名冊) ---
        user_ws = sheet.worksheet("Users")
        all_users = user_ws.get_all_values()
        
        # 找看看這個 ID 是否已經在表裡 (比對第 2 欄的使用者 ID)
        found_row_index = -1
        for i, row in enumerate(all_users):
            if len(row) > 1 and row[1] == user_id:
                found_row_index = i + 1
                break
        
        if found_row_index != -1:
            # 已存在，更新名稱、最後訊息、時間
            user_ws.update_cell(found_row_index, 3, user_name) # 更新名稱
            user_ws.update_cell(found_row_index, 4, now)       # 更新最後時間
        else:
            # 新面孔，新增一行
            user_ws.append_row([now, user_id, user_name, now, message])

    except Exception as e:
        logger.error(f"❌ 雲端紀錄失敗: {e}")


def log_user_info(event):
    """將發送訊息的使用者 ID 與名稱存入 CSV"""
    user_id = event.source.user_id
    display_name = "未知使用者"
    
    try:
        # 嘗試取得使用者名稱 (需機器人為好友或在同一群組)
        profile = line_bot_api.get_profile(user_id)
        display_name = profile.display_name
    except Exception:
        pass

    file_exists = os.path.isfile(USER_LOG_FILE)
    with open(USER_LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Timestamp', 'User_ID', 'Display_Name']) # 建立標頭
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, display_name])


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    group_id = event.source.group_id if event.source.type == 'group' else "私訊"

    user_name = "未知名稱"
    group_name = "個人對話"

    try:
        profile = line_bot_api.get_profile(user_id)
        user_name = profile.display_name
        if event.source.type == 'group':
            group_summary = line_bot_api.get_group_summary(group_id)
            group_name = group_summary.group_name
    except:
        pass # LINE 權限限制時保持預設值

    msg = event.message.text.strip()
    record_interaction(group_id, group_name, user_id, user_name, msg)
    
    trigger_keyword = "81人數助理"
    if trigger_keyword not in msg:
        return 

    user_query = msg.replace(trigger_keyword, "").strip()
    
    # 建立回應訊息
    reply_msgs = []

    # 便捷指令
    if user_query in ["更新", "更新資料"]:
        try:
            update_rag_context()
            reply_msgs.append(TextSendMessage(text="✅ 資料已更新！"))
        except Exception as e:
            reply_msgs.append(TextSendMessage(text=f"❌ 更新失敗: {e}"))
    
    elif user_query in ["幫助", "help", "說明"]:
        help_text = """🤖 81人數助理使用說明

📊 可用的查詢類型：
• 成員名單 - 查詢各小區成員
• 排行榜 - 查看出席積分排名
• 趨勢 - 分析出席趨勢
• 恢復資料 - 查詢可恢復成員
• 不穩定成員 - 查詢出席不穩定成員
• 更新 - 更新 RAG 知識庫

💡 自然語言查詢範例：
• 青年一區有多少人？
• 誰的出席率最高？
• 弟兄青職的成員有哪些？
• 最近幾週主日出席趨勢如何？
• 哪些成員需要關懷？
• 青年一區可恢復的成員有哪些？
• 誰最近缺席最多？

直接輸入您的問題即可！"""
        reply_msgs.append(TextSendMessage(text=help_text))
    
    else:
        # RAG 查詢
        try:
            res = generate_response(user_query)
            reply_msgs.append(TextSendMessage(text=res))
        except Exception as e:
            reply_msgs.append(TextSendMessage(text=f"❌ 查詢失敗: {e}"))

    # 發送回應
    if reply_msgs:
        try:
            line_bot_api.reply_message(event.reply_token, reply_msgs)
        except Exception as e:
            print(f"❌ LINE API 發送失敗: {e}")


if __name__ == "__main__":
    # 啟動時初始化 RAG 知識庫
    print("🚀 正在初始化 81人數助理...")
    try:
        update_rag_context()
    except Exception as e:
        print(f"⚠️ RAG 初始化失敗，將在首次查詢時重試: {e}")
    
    port = int(os.environ.get('PORT', 10000))
    print(f"✅ 服務啟動於 port {port}")
    app.run(host='0.0.0.0', port=port)
