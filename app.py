import os
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot.v3.webhook import WebhookHandler, Event
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging.models import TextMessage
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent, 
    TextMessage, 
    ImageMessage,    # Sidney新增：圖片訊息事件模型
    FileMessage,     # Sidney新增：檔案訊息事件模型
    TextSendMessage,
    ImageSendMessage)
from linebot.exceptions import InvalidSignatureError
import logging

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
line_bot_api = LineBotApi(line_token)
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


# 1. 設置一個事件處理器來處理 TextMessage 事件
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event: Event):

    # 2026/7/27 新增by Sidney，想查看message.type
    user_message_type = event.message.type # 使用者的訊息型態 (test / image / file / ?...)
    app.logger.info(f"收到的訊息type: {user_message_type}")

    user_message = event.message.text  # 使用者的訊息
    app.logger.info(f"收到的訊息: {user_message}")

    ## 使用 GPT 生成回應
    reply_text = ("LINEBot Test收到：" + user_message)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

        
# 2. 處理圖片訊息
@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    
    # 2026/7/27 新增by Sidney，想查看message.type
    user_message_type = event.message.type # 使用者的訊息型態 (test / image / file / ?...)
    app.logger.info(f"收到的訊息type: {user_message_type}")


    message_id = event.message.id
    app.logger.info(f"收到圖片訊息，Message ID: {message_id}")

    # 回覆使用者收到圖片
    reply_text = f"收到你的圖片囉！(Message ID: {message_id})"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )


# 3. 處理檔案訊息 (FileMessage)
@handler.add(MessageEvent, message=FileMessage)
def handle_file_message(event):
    
    # 2026/7/27 新增by Sidney，想查看message.type
    user_message_type = event.message.type # 使用者的訊息型態 (test / image / file / ?...)
    app.logger.info(f"收到的訊息type: {user_message_type}")
    
    
    message_id = event.message.id
    file_name = event.message.file_name  # 檔案名稱
    file_size = event.message.file_size  # 檔案大小 (Bytes)
    
    app.logger.info(f"收到檔案訊息: {file_name} ({file_size} bytes), Message ID: {message_id}")

    # 回覆使用者收到檔案
    reply_text = f"收到檔案囉！\n檔名：{file_name}\n大小：{file_size} bytes"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

        
# 應用程序入口點
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
