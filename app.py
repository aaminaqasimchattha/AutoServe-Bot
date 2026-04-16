from fastapi import FastAPI, Request, Response, Query
import requests
import os
import logging
import hmac
import hashlib
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load chat model dynamically to handle hyphenated directory name
ai_agent_path = Path(__file__).parent / "ai-agent"
if str(ai_agent_path) not in sys.path:
    sys.path.insert(0, str(ai_agent_path))

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("chat_model_module", ai_agent_path / "chat_model.py")
    if spec and spec.loader:
        chat_model_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(chat_model_module)
        get_chat_response = chat_model_module.get_chat_response
        initialize_model = chat_model_module.initialize_model
    else:
        raise ImportError("Could not load chat model")
except Exception as e:
    logging.error(f"Error loading chat model: {e}")
    # Fallback functions if model fails to load
    def get_chat_response(msg):
        return "Model loading failed. Please check logs."
    def initialize_model():
        return False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="WhatsApp Bot")

# ─── Initialize the chat model on startup ───────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting up WhatsApp Bot...")
    initialize_model()
    logger.info("✅ Bot startup complete!")

# ─── CONFIG — matches your .env exactly ───────────────────────────────────────
ACCESS_TOKEN    = os.getenv("ACCESS_TOKEN")
PHONE_ID        = os.getenv("PHONE_ID")
VERIFY_TOKEN    = os.getenv("VERIFY_TOKEN")
APP_SECRET      = os.getenv("APP_SECRET")

if not all([ACCESS_TOKEN, PHONE_ID, VERIFY_TOKEN]):
    logger.error("❌ Missing environment variables!")
    logger.error(f"  ACCESS_TOKEN: {'✓' if ACCESS_TOKEN else '✗ MISSING'}")
    logger.error(f"  PHONE_ID: {'✓' if PHONE_ID else '✗ MISSING'}")
    logger.error(f"  VERIFY_TOKEN: {'✓' if VERIFY_TOKEN else '✗ MISSING'}")
    logger.error(f"  APP_SECRET: {'✓' if APP_SECRET else '✗ MISSING'}")
else:
    logger.info("✅ All environment variables loaded!")
    logger.info(f"   PHONE_ID: {PHONE_ID}")
    logger.info(f"   VERIFY_TOKEN: {VERIFY_TOKEN}")
    logger.info(f"   APP_SECRET loaded: {'✓' if APP_SECRET else '✗ NOT SET'}")


@app.get("/")
async def health_check():
    return {
        "status": "Bot is running ✓",
        "environment": {
            "ACCESS_TOKEN": "✓" if ACCESS_TOKEN else "✗ MISSING",
            "PHONE_ID": "✓" if PHONE_ID else "✗ MISSING",
            "VERIFY_TOKEN": "✓" if VERIFY_TOKEN else "✗ MISSING",
            "APP_SECRET": "✓" if APP_SECRET else "✗ NOT SET",
        }
    }


@app.get("/webhook/test")
async def webhook_test():
    return {"status": "ok", "message": "Webhook test endpoint is working."}


@app.get("/debug")
async def debug():
    return {
        "message": "Debug endpoint",
        "ACCESS_TOKEN_set": bool(ACCESS_TOKEN),
        "PHONE_ID_set": bool(PHONE_ID),
        "VERIFY_TOKEN_set": bool(VERIFY_TOKEN),
        "webhook_url": "/webhook/whatsappbot/webhook"
    }


@app.get("/webhook/Whatsappbot/webhook")
async def verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    logger.info("🔐 Verification request received:")
    logger.info(f"   hub.mode        = {hub_mode}")
    logger.info(f"   hub.verify_token= {hub_verify_token}")
    logger.info(f"   hub.challenge   = {hub_challenge}")
    logger.info(f"   expected token  = {VERIFY_TOKEN}")

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully!")
        return Response(content=hub_challenge or "", media_type="text/plain")

    logger.warning("❌ Webhook verification failed")
    return Response(content="Forbidden", status_code=403)


@app.post("/webhook/Whatsappbot/webhook")
async def webhook(request: Request):
    try:
        headers = dict(request.headers)
        body = await request.body()

        logger.info(f"📥 Webhook received")

        if not body:
            logger.info("ℹ️ Empty request body - likely a status update from Meta")
            return {"status": "ok"}
        
        logger.info(f"📥 Webhook body raw: {body}")
        logger.info("✅ Webhook received - processing message")
            
        if APP_SECRET:
            signature_header = headers.get("x-hub-signature-256")
            if not signature_header:
                logger.warning("❌ Missing X-Hub-Signature-256 header")
                return Response(content="Missing signature", status_code=403)


            if not signature_header.startswith("sha256="):
                logger.warning("❌ Invalid X-Hub-Signature-256 format")
                return Response(content="Invalid signature format", status_code=403)

            received_signature = signature_header.split("=", 1)[1]
            expected_signature = hmac.new(
                APP_SECRET.encode("utf-8"),
                body,
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(received_signature, expected_signature):
                logger.warning("❌ Webhook signature mismatch")
                return Response(content="Invalid signature", status_code=403)

            logger.info("✅ Webhook signature verified")
        else:
            logger.warning("⚠️ APP_SECRET not set — skipping signature verification")

        data = await request.json()
        logger.info(f"📨 Incoming data: {data}")

        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if messages:
            message = messages[0]
            sender_number = message.get("from")
            message_type = message.get("type")

            if message_type == "text":
                user_text = message.get("text", {}).get("body", "")
                logger.info(f"💬 Message from {sender_number}: {user_text}")
                
                # Send acknowledgment that bot is processing
                send_whatsapp_message(sender_number, "⏳ Processing your message...")
                
                # Generate response using the seq2seq model
                bot_response = get_chat_response(user_text)
                logger.info(f"🤖 Bot response: {bot_response}")
                
                # Send the actual response
                send_whatsapp_message(sender_number, bot_response)
            else:
                logger.info(f"📦 Non-text message type: {message_type}")
                send_whatsapp_message(sender_number, "Sorry, I only support text messages!")
        else:
            logger.info("ℹ️ No messages — probably a status update, ignoring.")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


def send_whatsapp_message(to: str, text: str):
    url = f"https://graph.facebook.com/v25.0/1104882736033016/messages"
    headers = {
        "Authorization": f"Bearer {VERIFY_TOKEN}",
        "Content-Type": "application/json",
        "method": "POST"
    }
    payload = {
        "messaging_product": "whatsapp",   
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text
        }
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10, verify=False)
        logger.info(f"📤 Reply sent to {to} → Status: {res.status_code}")
        if res.status_code != 200:
            logger.error(f"❌ Failed: {res.text}")
        return res.json()

    except requests.exceptions.Timeout:
        logger.error("❌ Timeout!")
        return {"error": "Timeout"}
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error: {e}")
        return {"error": str(e)}


# Terminal 1: uvicorn app:app --reload --port 8000
# Terminal 2: ngrok http 8000 --domain circling-snowfall-emission.ngrok-free.dev
# Meta Dashboard Setup:
#   - Callback URL: https://circling-snowfall-emission.ngrok-free.dev/webhook
#   - Token: your VERIFY_TOKEN from .env
#   - Check: messages event
#   - Click: Verify and Save