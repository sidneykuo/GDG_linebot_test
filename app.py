import os
import logging
import io
import requests  # 引入 requests 用於下載 LINE CDN 的貼圖圖片

from dotenv import load_dotenv
from flask  import Flask, request, abort, send_from_directory
from PIL    import Image

# 引入 LINE SDK v3 的模組                  
from linebot.v3.webhook    import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging  import (
    Configuration
  , ApiClient
  , MessagingApi
  , MessagingApiBlob
  , ReplyMessageRequest                     
)

# 在 models 中引入 ImageMessage 與 TextMessage
from linebot.v3.messaging.models import TextMessage, ImageMessage

from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,    # 引入文字訊息型態
    ImageMessageContent,   # 引入圖形訊息型態
    FileMessageContent,    # 引入檔案訊息型態
    StickerMessageContent  # 引入貼圖訊息型態        
)

# 引入 .env 環境變數
load_dotenv()

# 從環境變數中讀取 LINE 的 Channel Access Token 和 Channel Secret
line_token = os.getenv('LINE_TOKEN')
line_secret = os.getenv('LINE_SECRET')

# 檢查是否設置了環境變數
if not line_token or not line_secret:
    raise ValueError("LINE_TOKEN 或 LINE_SECRET 未設置，請檢查 .env 檔案")

# 初始化 LINE SDK 物件
configuration = Configuration(access_token=line_token)
handler = WebhookHandler(line_secret)

# 創建 Flask 應用
app = Flask(__name__)
app.logger.setLevel(logging.INFO)
# app.logger.info(f"After logging level settiing")


# ==================== 全域檔案目錄設定 ====================
FILE_STORAGE_FOLDER="downloads"
FILE_PATH = os.path.join(app.root_path, FILE_STORAGE_FOLDER)
os.makedirs(FILE_PATH, exist_ok=True)  # 自動確保 FILE_STORAGE_FOLDER 目錄存在，存在則不重複建立


# 在所有 Request 進來時先執行的 Hook 函式
@app.before_request
def log_incoming_request():
    # 若此處夠清楚，下列幾行獨立的 logger.info 應該可以移掉
    app.logger.info(f"📥 [{request.method}] {request.path} | Remote IP: {request.remote_addr}")


# ==================== Helper 小幫手函式 -- BEGIN ====================
def get_source_info(event):
    """安全取得 User ID 和 Group ID(群組ID) 和Room ID(多人聊天室ID)"""
    user_id = getattr(event.source, 'user_id', None)
    group_id = getattr(event.source, 'group_id', None)

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
# ==================== Helper 小幫手函式 -- END ====================



# ========== 設置 Webhook 路由 來處理 LINE Webhook 的回調請求 ==========
@app.route("/", methods=['POST'])
def callback():
    # 取得 X-Line-Signature 標頭
    signature = request.headers.get('X-Line-Signature', '')
    
    # 取得請求的原始內容
    body = request.get_data(as_text=True)
    # app.logger.info(f"Request body: {body}")

    # 驗證簽名並處理請求
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


# 提供儲存檔案對外公開下載的靜態檔案路由
@app.route(f'/{FILE_STORAGE_FOLDER}/<filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(FILE_PATH, filename)



# ==================== 事件處理器 (Event Handlers) ====================

# Handler_1. 處理文字訊息
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    details = get_source_info(event)   # 呼叫Helper小幫手抓出使用者資訊
    user_info  = f"{details['user_name']} ({details['user_id']})" if details['user_name'] else details['user_id']
    group_info = f"{details['group_name']} ({details['group_id']})" if details['group_name'] else (details['group_id'] or "None")
    
    user_message_type = event.message.type # 使用者的訊息型態 (此處應為text)
    message_id = event.message.id          # 使用者的訊息ID
    user_message = event.message.text      # 使用者的訊息文字

    app.logger.info(f"完整 Event 內容: {event}")
    app.logger.info(f"MsgType: {user_message_type} | MsgID: {message_id} | UsrInfo: {user_info} | GrpInfo: {group_info} | Text: {user_message}")

    reply_text = (
        f"LINEBot 收到文字\n"
        f"  --User Info ：{user_info}\n"
        f"  --Group Info：{group_info}\n"
        f"  --Message ID: {message_id}\n"
        f"  --文字訊息: {user_message}"
    )
    
    reply_text_message(event.reply_token, reply_text)


# Handler_2. 處理圖片訊息 (自動轉檔為 JPG 以相容所有圖片格式)
@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    details = get_source_info(event)   # 呼叫Helper小幫手抓出使用者資訊
    user_info  = f"{details['user_name']} ({details['user_id']})" if details['user_name'] else details['user_id']
    group_info = f"{details['group_name']} ({details['group_id']})" if details['group_name'] else (details['group_id'] or "None")
    
    user_message_type = event.message.type # 使用者的訊息型態 (此處應為image)
    message_id = event.message.id          # 使用者的訊息ID

    app.logger.info(f"完整 Event 內容: {event}")
    app.logger.info(f"MsgType: {user_message_type} | MsgID: {message_id} | UsrInfo: {user_info} | GrpInfo: {group_info}")

    saved_filename = f"{message_id}.jpg"
    save_path = os.path.join(FILE_PATH, saved_filename)

    # 載圖片並利用 Pillow 轉檔為標準 JPEG 格式 (相容 BMP, GIF, PNG, JPG)
    with ApiClient(configuration) as api_client:
        blob_api = MessagingApiBlob(api_client)
        content = blob_api.get_message_content(message_id)
        
        try:
            # 用 Pillow 開啟記憶體中的二進位圖片
            image = Image.open(io.BytesIO(content))
            # 若為 RGBA (例如透明 PNG) 或 P 模式 (例如 GIF/BMP)，先轉為 RGB 才能存成 JPG
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            # 統一儲存為 JPEG 格式
            image.save(save_path, "JPEG")
        except Exception as e:
            app.logger.error(f"圖片轉檔失敗，改直接寫入原檔: {e}")
            with open(save_path, "wb") as f:
                f.write(content)

    # 產生公開存取的 HTTPS 圖檔網址
    base_url = request.host_url.replace("http://", "https://")
    image_url = f"{base_url}{FILE_STORAGE_FOLDER}/{saved_filename}"

    # 組裝資訊文字
    reply_text = (
        f"LINEBot 收到圖片\n"
        f"  --User Info ：{user_info}\n"
        f"  --Group Info：{group_info}\n"
        f"  --Message ID: {message_id}\n"
        f"  --檔名：圖檔無檔名資訊\n"
        f"  --大小：圖檔無大小資訊"
    )

    # 回覆「說明文字」與「圖片訊息 (ImageMessage)」給發送者/群組
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=reply_text),
                    ImageMessage(
                        original_content_url=image_url, # 原圖網址
                        preview_image_url=image_url     # 預覽圖網址
                    )
                ]
            )
        )


# Handler_3. 處理檔案訊息 (儲存檔案並回傳公開下載網址)
@handler.add(MessageEvent, message=FileMessageContent)
def handle_file_message(event):
    details = get_source_info(event)   # 呼叫Helper小幫手抓出使用者資訊
    user_info  = f"{details['user_name']} ({details['user_id']})" if details['user_name'] else details['user_id']
    group_info = f"{details['group_name']} ({details['group_id']})" if details['group_name'] else (details['group_id'] or "None")
    
    user_message_type = event.message.type # 使用者的訊息型態 (此處應為file)
    message_id = event.message.id          # 使用者的訊息ID
    file_name = event.message.file_name    # 檔案名稱
    file_size = event.message.file_size    # 檔案Size

    app.logger.info(f"完整 Event 內容: {event}")
    app.logger.info(f"MsgType: {user_message_type} | MsgID: {message_id} | UsrInfo: {user_info} | GrpInfo: {group_info} | Name: {file_name} ({file_size} bytes)")

    # 用 message_id 作為檔名前綴，避免同名檔案覆蓋問題
    saved_filename = f"{message_id}_{file_name}"
    save_path = os.path.join(FILE_PATH, saved_filename)

    with ApiClient(configuration) as api_client:
        blob_api = MessagingApiBlob(api_client)
        content = blob_api.get_message_content(message_id)
        with open(save_path, "wb") as f:
            f.write(content)

    # 生成 Render 上的公開存取網址 (自動偵測當前功能網域並補上 HTTPS)
    base_url = request.host_url.replace("http://", "https://")
    file_url = f"{base_url}{FILE_STORAGE_FOLDER}/{saved_filename}"

    # 組裝原本要回覆的文字訊息，並附上下載網址
    reply_text = (
        f"LINEBot 收到檔案\n"
        f"  --User Info ：{user_info}\n"
        f"  --Group Info：{group_info}\n"
        f"  --Message ID: {message_id}\n"
        f"  --檔名：{file_name}\n"
        f"  --大小：{file_size} bytes\n"
        f"  --檔案下載網址：\n{file_url}"
    )

    app.logger.info(f"reply_text: {reply_text}")
    
    # 回覆給發送者/群組
    reply_text_message(event.reply_token, reply_text)


# Handler_4. 處理貼圖訊息
@handler.add(MessageEvent, message=StickerMessageContent)
def handle_sticker_message(event):
    details = get_source_info(event)
    user_info  = f"{details['user_name']} ({details['user_id']})" if details['user_name'] else details['user_id']
    group_info = f"{details['group_name']} ({details['group_id']})" if details['group_name'] else (details['group_id'] or "None")
    
    user_message_type = event.message.type
    message_id = event.message.id
    
    # 抓取貼圖的元資料 (Metadata)
    sticker_id = event.message.sticker_id  # 貼圖ID
    package_id = event.message.package_id  # 貼圖包ID
    sticker_resource_type = getattr(event.message, 'sticker_resource_type', 'STATIC') # 貼圖類型
    keywords = getattr(event.message, 'keywords', None)       #貼圖關鍵字
    keywords_str = ", ".join(keywords) if keywords else "無"  #貼圖關鍵字從List解析為逗號分隔

    # 用 message_id 與 sticker_id 作為檔名，並統一轉檔存成 JPG
    saved_filename = f"{message_id}_{sticker_id}.jpg"
    save_path = os.path.join(FILE_PATH, saved_filename)

    # 從 LINE 官方 CDN 下載貼圖圖片（預設為 PNG 格式）
    cdn_sticker_url = f"https://stickershop.line-scdn.net/stickershop/v1/sticker/{sticker_id}/android/sticker.png"
    
    try:
        response = requests.get(cdn_sticker_url)
        if response.status_code == 200:
            # 用 Pillow 開啟 PNG 圖片
            image = Image.open(io.BytesIO(response.content))
            
            # 若為帶透明圖層的圖片 (RGBA, LA, P 模式)，建立白色底圖進行合成，防止透明處變黑
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
                background = Image.new("RGBA", image.size, (255, 255, 255, 255))
                composite_image = Image.alpha_composite(background, image)
                final_image = composite_image.convert("RGB")
                final_image.save(save_path, "JPEG")
            else:
                image.save(save_path, "JPEG")
        else:
            app.logger.error(f"下載貼圖失敗，HTTP 狀態碼: {response.status_code}")
    except Exception as e:
        app.logger.error(f"下載或轉檔貼圖失敗: {e}")

    # 產生 Render 上公開存取的 HTTPS 圖檔網址
    base_url = request.host_url.replace("http://", "https://")
    image_url = f"{base_url}{FILE_STORAGE_FOLDER}/{saved_filename}"
    
    app.logger.info(f"完整 Event 內容: {event}")
    app.logger.info(f"MsgType: {user_message_type} | MsgID: {message_id} | UsrInfo: {user_info} | GrpInfo: {group_info} | StickerID: {sticker_id} | PackageID: {package_id}")

    # 組裝資訊文字
    reply_text = (
        f"LINEBot 收到貼圖\n"
        f"  --User Info ：{user_info}\n"
        f"  --Group Info：{group_info}\n"
        f"  --Message ID: {message_id}\n"
        f"  --Package ID: {package_id}\n"
        f"  --Sticker ID: {sticker_id}\n"
        f"  --貼圖類型: {sticker_resource_type}\n"
        f"  --關鍵字: {keywords_str}\n"
        f"  --貼圖圖片網址：\n{image_url}"
    )
    
    # 回覆「說明文字」與下載下來的「貼圖圖片 (ImageMessage)」給發送者/群組
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=reply_text),
                    ImageMessage(
                        original_content_url=image_url, # 原圖網址
                        preview_image_url=image_url     # 預覽圖網址
                    )
                ]
            )
        )


# 應用程序入口點(僅在用 `python3 app.py` 直接啟動時生效)
if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
