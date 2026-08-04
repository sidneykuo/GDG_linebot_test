import os
import logging
from dotenv import load_dotenv
from flask import Flask, request, abort, send_from_directory

# 引入 LINE SDK v3 的模組
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest
)

# 只引入官方支援的 TextMessage
from linebot.v3.messaging.models import TextMessage

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

    user_name = None
    group_name = None

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # 1. 嘗試取得 User Name (使用者名稱/暱稱)
        if user_id:
            try:
                if group_id:
                    # 如果在群組內，取得該群組成員的名單資料
                    member_profile = line_bot_api.get_group_member_profile(group_id, user_id)
                    user_name = member_profile.display_name
                else:
                    # 如果是一對一私訊
                    profile = line_bot_api.get_profile(user_id)
                    user_name = profile.display_name
            except Exception as e:
                app.logger.error(f"無法取得 User Name: {e}")

        # 2. 嘗試取得 Group Name (群組名稱)
        if group_id:
            try:
                group_summary = line_bot_api.get_group_summary(group_id)
                group_name = group_summary.group_name
            except Exception as e:
                app.logger.error(f"無法取得 Group Name: {e}")

    return {
        "user_id": user_id,
        "user_name": user_name,
        "group_id": group_id,
        "group_name": group_name,
        "room_id": room_id
    }

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


# 提供儲存檔案對外公開下載的靜態檔案路由
@app.route('/downloads/<filename>', methods=['GET'])
def download_file(filename):
    download_dir = os.path.join(app.root_path, 'downloads')
    return send_from_directory(download_dir, filename)


# ==================== 事件處理器 (Event Handlers) ====================

# 1. 處理文字訊息
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    details = get_source_info(event)   # 呼叫Helper小幫手抓出使用者資訊
    user_info  = f"{details['user_name']} ({details['user_id']})" if details['user_name'] else details['user_id']
    group_info = f"{details['group_name']} ({details['group_id']})" if details['group_name'] else (details['group_id'] or "None")
    room_id = f"{details['room_id']}"
    
    user_message_type = event.message.type # 使用者的訊息型態 (此處應為text)
    message_id = event.message.id          # 使用者的訊息ID
    user_message = event.message.text      # 使用者的訊息文字

    app.logger.info(f"完整 Event 內容: {event}")
    app.logger.info(f"MsgType: {user_message_type} | MsgID: {message_id} | UsrInfo: {user_info} | GrpInfo: {group_info} | RoomID: {room_id} | Text: {user_message}")

    reply_text = (
        f"LINEBot 收到文字\n"
        #### 暫時保留以下兩行以備不時之需
        #### f"  --User ID: {user_id}\n"
        #### f"  --Group ID: {group_id}\n"
        f"  --User Info ：{user_info}\n"
        f"  --Group Info：{group_info}\n"
        f"  --Room ID: {room_id}\n"
        f"  --Message ID: {message_id}\n"
        f"  --文字訊息: {user_message}"
    )
    
    reply_text_message(event.reply_token, reply_text)


# 2. 處理圖片訊息
@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    details = get_source_info(event)   # 呼叫Helper小幫手抓出使用者資訊
    user_info  = f"{details['user_name']} ({details['user_id']})" if details['user_name'] else details['user_id']
    group_info = f"{details['group_name']} ({details['group_id']})" if details['group_name'] else (details['group_id'] or "None")
    room_id = f"{details['room_id']}"
    
    user_message_type = event.message.type # 使用者的訊息型態 (此處應為image)
    message_id = event.message.id          # 使用者的訊息ID

    app.logger.info(f"完整 Event 內容: {event}")
    app.logger.info(f"MsgType: {user_message_type} | MsgID: {message_id} | UsrInfo: {user_info} | GrpInfo: {group_info} | RoomID: {room_id}")

    reply_text = (
        f"LINEBot 收到圖片\n"
        f"  --User Info ：{user_info}\n"
        f"  --Group Info：{group_info}\n"
        f"  --Room ID: {room_id}\n"
        f"  --Message ID: {message_id}\n"
        f"  --檔名：圖檔無檔名資訊\n"
        f"  --大小：圖檔無大小資訊"
    )

    reply_text_message(event.reply_token, reply_text)


# 3. 處理檔案訊息 (儲存檔案並回傳公開下載網址)
@handler.add(MessageEvent, message=FileMessageContent)
def handle_file_message(event):
    details = get_source_info(event)   # 呼叫Helper小幫手抓出使用者資訊
    user_info  = f"{details['user_name']} ({details['user_id']})" if details['user_name'] else details['user_id']
    group_info = f"{details['group_name']} ({details['group_id']})" if details['group_name'] else (details['group_id'] or "None")
    room_id = f"{details['room_id']}"
    
    user_message_type = event.message.type # 使用者的訊息型態 (此處應為file)
    message_id = event.message.id          # 使用者的訊息ID
    file_name = event.message.file_name    # 檔案名稱
    file_size = event.message.file_size    # 檔案Size

    app.logger.info(f"完整 Event 內容: {event}")
    app.logger.info(f"MsgType: {user_message_type} | MsgID: {message_id} | UsrInfo: {user_info} | GrpInfo: {group_info} | RoomID: {room_id} | Name: {file_name} ({file_size} bytes)")

    # 1. 建立下載目錄並儲存從 LINE 取得的檔案
    download_dir = "downloads"
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    # 用 message_id 作為檔名前綴，避免同名檔案覆蓋問題
    saved_filename = f"{message_id}_{file_name}"
    save_path = os.path.join(download_dir, saved_filename)

    with ApiClient(configuration) as api_client:
        blob_api = MessagingApiBlob(api_client)
        content = blob_api.get_message_content(message_id)
        with open(save_path, "wb") as f:
            f.write(content)

    # 2. 生成 Render 上的公開存取網址 (自動偵測當前功能網域並補上 HTTPS)
    base_url = request.host_url.replace("http://", "https://")
    file_url = f"{base_url}downloads/{saved_filename}"

    # 3. 組裝原本要回覆的文字訊息，並附上下載網址
    reply_text = (
        f"LINEBot 收到檔案\n"
        f"  --User Info ：{user_info}\n"
        f"  --Group Info：{group_info}\n"
        f"  --Room ID: {room_id}\n"
        f"  --Message ID: {message_id}\n"
        f"  --檔名：{file_name}\n"
        f"  --大小：{file_size} bytes\n"
        f"  --檔案下載網址：\n{file_url}"
    )

    # 4. 回覆給發送者/群組
    reply_text_message(event.reply_token, reply_text)


# 應用程序入口點
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
