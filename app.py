import os
import logging
from dotenv import load_dotenv
from flask import Flask, request, abort

# 引入 LINE SDK v3 的模組
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    FileMessageContent
)

# 1. 加載 .env 環境變數
load_dotenv()

# 從環境變數中讀取 LINE 的 Channel Access Token 和 Channel Secret
line_token = os.getenv('LINE_TOKEN')
line_secret = os.getenv('LINE_SECRET')

# 檢查是否設置了環境變數
if not line_token or not line_secret:
    ## 以下兩行被Gemini移除，不確定是否是多餘的?? 待研究
    ## print(f"LINE_TOKEN: {line_token}")  # 調試輸出
    ## print(f"LINE_SECRET: {line_secret}")  # 調試輸出
    raise ValueError("LINE_TOKEN 或 LINE_SECRET 未設置，請檢查 .env 檔案")

# 2. 初始化 LINE SDK 物件
configuration = Configuration(access_token=line_token)
handler = WebhookHandler(line_secret)

# 3. 創建 Flask 應用
app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)


# ==================== Helper 小幫手函式 ====================

def get_source_info(event):
    """安全取得 User ID 和 Group ID(群組ID) 和Room ID(多人聊天室ID)"""
    user_id = getattr(event.source, 'user_id', None)
    group_id = getattr(event.source, 'group_id', None)
    room_id = getattr(event.source, 'room_id', None)
    return user_id, group_id, room_id


def reply_text_message(event_reply_token: str, text: str):
    """統一封裝回覆訊息邏輯，避免程式碼重複"""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event_reply_token,
                messages=[TextMessage(text=text)]
            )
        )


# ========== 設置 Webhook 路由 來處理 LINE Webhook 的回調請求 ==========
@app.route("/", methods=['POST'])
def callback():
    # 取得 X-Line-Signature 標頭
    signature = request.headers.get('X-Line-Signature', '')
    
    # 取得請求的原始內容
    body = request.get_data(as_text=True)
    app.logger.info(f"Request body: {body}")

    # 驗證簽名並處理請求
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


# ==================== 事件處理器 (Event Handlers) ====================

# 1. 處理文字訊息
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_id, group_id, room_id = get_source_info(event) # 呼叫Helper小幫手抓出使用者資訊
    user_message_type = event.message.type # 使用者的訊息型態 (此處應為text)
    message_id = event.message.id          # 使用者的訊息ID
    user_message = event.message.text      # 使用者的訊息文字
    
    app.logger.info(f"MsgType: {user_message_type} | MsgID: {message_id} | UsrID: {user_id} | GrpID: {group_id} | RoomID: {room_id} | Text: {user_message}")

    reply_text = (
        f"LINEBot 收到文字\n"
        f"  User ID: {user_id}\n"
        f"  Group ID: {group_id}\n"
        f"  Room ID: {room_id}\n"
        f"  Message ID: {message_id}\n"
        f"  內容: {user_message}"
    )
    
    reply_text_message(event.reply_token, reply_text)


# 2. 處理圖片訊息
@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    user_id, group_id, room_id = get_source_info(event) # 呼叫Helper小幫手抓出使用者資訊
    user_message_type = event.message.type # 使用者的訊息型態 (此處應為image)
    message_id = event.message.id          # 使用者的訊息ID

    app.logger.info(f"MsgType: {user_message_type} | MsgID: {message_id} | UsrID: {user_id} | GrpID: {group_id} | RoomID: {room_id} | Text: {user_message}")

    reply_text = (
        f"LINEBot 收到圖片\n"
        f"  User ID: {user_id}\n"
        f"  Group ID: {group_id}\n"
        f"  Room ID: {room_id}\n"
        f"  Message ID: {message_id}\n"
        f"  檔名：n/a\n大小：n/a bytes"
    )

    reply_text_message(event.reply_token, reply_text)


# 3. 處理檔案訊息
@handler.add(MessageEvent, message=FileMessageContent)
def handle_file_message(event):
    user_id, group_id, room_id = get_source_info(event) # 呼叫Helper小幫手抓出使用者資訊
    user_message_type = event.message.type # 使用者的訊息型態 (此處應為file)
    message_id = event.message.id          # 使用者的訊息ID
    file_name = event.message.file_name    # 檔案名稱
    file_size = event.message.file_size    # 檔案Size

    app.logger.info(f"MsgType: {user_message_type} | MsgID: {message_id} | UsrID: {user_id} | GrpID: {group_id} | RoomID: {room_id} | Name: {file_name} ({file_size} bytes)")

    reply_text = (
        f"LINEBot 收到檔案\n"
        f"  User ID: {user_id}\n"
        f"  Group ID: {group_id}\n"
        f"  Room ID: {room_id}\n"
        f"  Message ID: {message_id}\n"
        f"  檔名：{file_name}\n"
        f"  大小：{file_size} bytes"
    )

    reply_text_message(event.reply_token, reply_text)


# 應用程序入口點
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
