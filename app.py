import os
import logging
from dotenv import load_dotenv
from flask  import Flask, request, abort

# 引入 LINE SDK v3 的模組
from linebot.v3.webhook    import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging  import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks   import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    FileMessageContent
)


# 加載 .env 文件中的變數
load_dotenv()

# 從環境變數中讀取 LINE 的 Channel Access Token 和 Channel Secret
line_token = os.getenv('LINE_TOKEN')
line_secret = os.getenv('LINE_SECRET')

# 檢查是否設置了環境變數
if not line_token or not line_secret:
    print(f"LINE_TOKEN: {line_token}")  # 調試輸出
    print(f"LINE_SECRET: {line_secret}")  # 調試輸出
    raise ValueError("LINE_TOKEN 或 LINE_SECRET 未設置")

# 初始化 LineBotApi 和 WebhookHandler
## line_bot_api = LineBotApi(line_token)
## handler = WebhookHandler(line_secret)
configuration = Configuration(access_token=line_token)
handler = WebhookHandler(line_secret)

# 創建 Flask 應用
app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)

# 設置一個路由來處理 LINE Webhook 的回調請求
@app.route("/", methods=['POST'])
def callback():
    # 取得 X-Line-Signature 標頭
    signature = request.headers['X-Line-Signature']

    # 取得請求的原始內容
    body = request.get_data(as_text=True)
    app.logger.info(f"Request body: {body}")

    # 驗證簽名並處理請求
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# Helper 函式：用來安全取得 User ID 和 Group ID(群組ID) 和Room ID(多人聊天室ID)
def get_source_info(event):
    user_id  = getattr(event.source, 'user_id', None)
    group_id = getattr(event.source, 'group_id', None)
    room_id  = getattr(event.source, 'room_id', None)
    return user_id, group_id


# 1. 設置一個事件處理器來處理 TextMessageContent 事件
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_message_type = event.message.type # 使用者的訊息型態 (此處應為text)
    message_id = event.message.id          # 使用者的訊息ID
    user_message = event.message.text      # 使用者的訊息
    
    app.logger.info(f"收到的訊息type: {user_message_type}")
    app.logger.info(f"收到的訊息id: {message_id}")
    app.logger.info(f"收到文字: {user_message}")

    # 生成回應
    reply_text = f"LINEBot 收到文字\nUser ID: {user_id}\nGroup ID: {group_id}\nRoom ID: {room_id}\nMessage ID: {message_id}\n內容: {user_message}"
    
    # v3 回覆訊息的寫法
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )
        
# 2. 處理圖片訊息
## @handler.add(MessageEvent, message=ImageMessage)
@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    
    # 印出message.type
    user_message_type = event.message.type # 使用者的訊息型態 (此處應為image)
    message_id = event.message.id          # 使用者的訊息ID

    app.logger.info(f"收到的訊息type: {user_message_type}")
    app.logger.info(f"收到的訊息id: {message_id}") 
    app.logger.info(f"收到圖片")

    # 回覆使用者收到圖片
    reply_text = f"LINEBot 收到圖片\nMessage ID: {message_id}\n檔名：n/a\n大小：n/a bytes"
    ## line_bot_api.reply_message(
    ##     event.reply_token,
    ##     TextSendMessage(text=reply_text)
    ## )

    # v3 回覆訊息的寫法
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )


# 3. 處理檔案訊息 (FileMessage)
## @handler.add(MessageEvent, message=FileMessage)
@handler.add(MessageEvent, message=FileMessageContent)

def handle_file_message(event):
    
    # 印出message.type
    user_message_type = event.message.type # 使用者的訊息型態 (此處應為file)
    message_id = event.message.id          # 使用者的訊息ID    
    file_name  = event.message.file_name   # 檔案名稱
    file_size  = event.message.file_size   # 檔案大小 (Bytes)
    app.logger.info(f"收到的訊息type: {user_message_type}")
    app.logger.info(f"收到的訊息id: {message_id}") 
    app.logger.info(f"收到檔案(v3): {file_name} ({file_size} bytes)")

    # 回覆使用者收到檔案
    reply_text = f"LINEBot 收到檔案\nMessage ID: {message_id}\n檔名：{file_name}\n大小：{file_size} bytes"
    
    ## line_bot_api.reply_message(
    ##     event.reply_token,
    ##     TextSendMessage(text=reply_text)
    ## )
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

# 應用程序入口點
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
