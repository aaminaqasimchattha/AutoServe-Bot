from fastapi import FastAPI, Request, Response, Query
import requests
import os
import logging
import hmac
import hashlib
import sys
from pathlib import Path
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
import re
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load chat model dynamically from hyphenated folder name: ai-agent
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
        raise ImportError("Could not load chat model module spec")
except Exception as e:
    logger.error(f"Model import failed: {e}")

    def get_chat_response(_sender_number: str, _msg: str) -> str:
        return "Model loading failed. Please try again later."

    def initialize_model() -> bool:
        return False

load_dotenv()

# Gmail SMTP / OAuth / human agent configuration
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
HUMAN_AGENT_EMAIL = os.getenv("HUMAN_AGENT_EMAIL") or "kashifabdulbasit@gmail.com"
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")

# In-memory per-sender state to track greeting choices
pending_choice = {}

app = FastAPI(title="WhatsApp Bot")

def get_gmail_access_token() -> Optional[str]:
    global REFRESH_TOKEN
    if not CLIENT_ID or not CLIENT_SECRET or not REFRESH_TOKEN:
        return None
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    try:
        res = requests.post(token_url, data=payload)
        return res.json().get("access_token")
    except Exception as e:
        logger.error(f"Failed to refresh access token: {e}")
        return None

def send_email_via_gmail_api(to_email: str, subject: str, body: str) -> bool:
    access_token = get_gmail_access_token()
    if not access_token:
        logger.warning("Could not refresh access token.")
        return False

    import base64
    from email.mime.text import MIMEText

    message = MIMEText(body)
    message["To"] = to_email
    message["Subject"] = subject
    
    # URL-safe base64 encoding for Gmail API
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    
    send_url = "https://www.googleapis.com/gmail/v1/users/me/messages/send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(send_url, headers=headers, json={"raw": raw_message})
        if res.status_code == 200:
            logger.info("Email sent via Gmail API successfully!")
            return True
        else:
            logger.error(f"Error sending email via Gmail API: {res.text}")
            return False
    except Exception as e:
        logger.error(f"Exception sending email via Gmail API: {e}")
        return False

@app.get("/gmail/auth")
async def gmail_auth(request: Request):
    if not CLIENT_ID or not CLIENT_SECRET:
        return {"error": "CLIENT_ID or CLIENT_SECRET is missing in .env"}
    
    redirect_uri = str(request.url_for("oauth2_callback"))
    if "ngrok" in redirect_uri and redirect_uri.startswith("http://"):
        redirect_uri = redirect_uri.replace("http://", "https://")
        
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?scope=https://www.googleapis.com/auth/gmail.send"
        "&access_type=offline"
        "&prompt=consent"
        "&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&client_id={CLIENT_ID}"
    )
    return {
        "instructions": (
            "1. Ensure the redirect_uri below is added to your Google Developer Console "
            "under Authorized redirect URIs for your Client ID.\n"
            f"Authorized Redirect URI: {redirect_uri}\n"
            "2. Open the authorization_url to log in and authorize the Gmail sending scope."
        ),
        "redirect_uri": redirect_uri,
        "authorization_url": auth_url
    }

@app.get("/oauth2callback")
async def oauth2_callback(request: Request, code: Optional[str] = None):
    global REFRESH_TOKEN
    if not code:
        return {"error": "Authorization code not provided by Google"}
        
    if not CLIENT_ID or not CLIENT_SECRET:
        return {"error": "CLIENT_ID or CLIENT_SECRET is missing in .env"}
        
    redirect_uri = str(request.url_for("oauth2_callback"))
    if "ngrok" in redirect_uri and redirect_uri.startswith("http://"):
        redirect_uri = redirect_uri.replace("http://", "https://")
        
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    
    try:
        res = requests.post(token_url, data=payload)
        token_data = res.json()
        
        if "refresh_token" in token_data:
            refresh_token = token_data["refresh_token"]
            
            # Save the refresh_token to .env
            env_path = Path(__file__).parent / ".env"
            env_content = env_path.read_text(encoding="utf-8")
            
            # Remove any existing REFRESH_TOKEN line
            lines = [line for line in env_content.splitlines() if not line.strip().startswith("REFRESH_TOKEN=")]
            lines.append(f"REFRESH_TOKEN={refresh_token}")
            
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            
            REFRESH_TOKEN = refresh_token
            os.environ["REFRESH_TOKEN"] = refresh_token
            
            return {
                "status": "success",
                "message": "Gmail OAuth refresh token has been saved to your .env file and loaded in memory! You can now send emails via the Gmail API."
            }
        else:
            return {
                "error": "Failed to obtain refresh token",
                "google_response": token_data
            }
    except Exception as e:
        return {"error": f"Error during token exchange: {str(e)}"}

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


@app.on_event("startup")
async def startup_event():
    logger.info("Starting WhatsApp bot...")
    initialize_model()
    logger.info("Startup complete")


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
        "webhook_url": "/webhook/whatsapp/webhook"
    }


@app.get("/webhook/Whatsapp/webhook")
@app.get("/webhook/Whatsapp/webhook")
async def verify(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge")
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


processed_message_ids = set()


@app.post("/webhook/Whatsapp/webhook")
@app.post("/webhook/Whatsapp/webhook")
async def webhook(request: Request):
    global processed_message_ids
    try:
        headers = dict(request.headers)
        body = await request.body()

        logger.info(f"📥 Webhook headers: {headers}")
        logger.info(f"📥 Webhook body raw: {body}")

        if not body:
            logger.warning("⚠️ Empty request body")
            return {"status": "ok"}

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
        
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        # Ignore statuses completely
        if "statuses" in value:
            return {"status": "ok"}

        messages = value.get("messages", [])


        if messages:
            message = messages[0]
            message_id = message.get("id")

            if message_id and message_id in processed_message_ids:
                logger.info(f"🔄 Duplicate message {message_id} received, skipping.")
                return {"status": "ok"}
            
            if message_id:
                processed_message_ids.add(message_id)

            sender_number = message.get("from")
            message_type = message.get("type")


            if message_type == "text":
                user_text = message.get("text", {}).get("body", "")
                print(f"\n=======================================================")
                print(f"💬 User {sender_number} says: {user_text}")
                logger.info(f"💬 User {sender_number} says: {user_text}")

                # Greeting and human-request detection
                def is_greeting(s: str) -> bool:
                    g = ["hi", "hello", "hey", "hiya", "greetings"]
                    txt = (s or "").strip().lower()
                    for w in g:
                        if txt == w or txt.startswith(w + " ") or (" " + w + " ") in (" " + txt + " "):
                            return True
                    return False

                def is_human_request(s: str) -> bool:
                    txt = (s or "").strip().lower()
                    patterns = [
                        "i want to talk to human",
                        "want to talk to human",
                        "talk to human",
                        "human agent",
                        "connect me to human",
                        "connect me to a human",
                        "live agent",
                        "real person",
                        "support agent",
                        "human support",
                    ]
                    if txt in ("2", "human", "agent", "support", "type two", "option 2"):
                        return True
                    if "human" in txt or "agent" in txt or "person" in txt:
                        return True
                    return any(p in txt for p in patterns)

                def extract_order_id(s: str) -> str:
                    if not s:
                        return ""
                    match = re.search(r"\bORD-\d{4,}\b", s, flags=re.IGNORECASE)
                    return match.group(0).upper() if match else ""

                def is_successful_order_placement(reply_text: str) -> bool:
                    txt = (reply_text or "").strip().lower()
                    return ("order placed" in txt or "success: order placed" in txt) and bool(extract_order_id(reply_text))

                def send_email_via_gmail(to_email: str, subject: str, body: str) -> bool:
                    if not GMAIL_USER or not GMAIL_APP_PASSWORD or not to_email:
                        logger.warning("Gmail sender, app password, or destination email not set")
                        return False
                    message = MIMEText(body)
                    message["From"] = GMAIL_USER
                    message["To"] = to_email
                    message["Subject"] = subject
                    try:
                        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
                            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                            server.send_message(message)
                        logger.info("Gmail notification sent successfully")
                        return True
                    except Exception as e:
                        logger.error(f"Error sending email via Gmail SMTP: {e}")
                        return False

                txt_lower = user_text.strip().lower()

                # Human request can be direct or follow the menu
                state = pending_choice.get(sender_number)
                if state == "awaiting_choice" and txt_lower in ("1", "chatbot", "bot", "ai", "type one", "option 1"):
                    bot_reply = "Hi there, I'm Zara, the chatbot. How can I help you?"
                    pending_choice.pop(sender_number, None)
                    send_whatsapp_message(sender_number, bot_reply)

                elif is_human_request(user_text):
                    use_gmail_api = bool(CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN)
                    use_smtp = bool(GMAIL_USER and GMAIL_APP_PASSWORD)
                    
                    if use_gmail_api or use_smtp:
                        subject = f" Human Agent Requested - {sender_number}"
                        body = (
                            "═══════════════════════════════════════════════════════\n"
                            "                   AUTOSERVE - SUPPORT ALERT\n"
                            "═══════════════════════════════════════════════════════\n\n"
                            "A customer has requested to speak with a human agent.\n\n"
                            "─────────────────────────────────────────────────────\n"
                            "CUSTOMER DETAILS:\n"
                            "─────────────────────────────────────────────────────\n"
                            f"Phone Number:    {sender_number}\n"
                            f"Contact Method:  WhatsApp\n"
                            f"Request Time:    {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                            "─────────────────────────────────────────────────────\n"
                            "CUSTOMER MESSAGE:\n"
                            "─────────────────────────────────────────────────────\n"
                            f"{user_text}\n\n"
                            "─────────────────────────────────────────────────────\n"
                            "ACTION REQUIRED:\n"
                            "─────────────────────────────────────────────────────\n"
                            "1. Review the customer's request above\n"
                            "2. Contact the customer at the phone number provided\n"
                            "3. Provide professional support and assistance\n"
                            "4. Ensure customer satisfaction\n\n"
                            "Thank you for providing excellent customer service!\n\n"
                            "───────────────────────────────────────────────────────\n"
                            "AUTOSERVE - Customer Support System\n"
                            "© 2026 All Rights Reserved\n"
                            "═══════════════════════════════════════════════════════"
                        )
                        if use_gmail_api:
                            ok = send_email_via_gmail_api(HUMAN_AGENT_EMAIL, subject, body)
                        else:
                            ok = send_email_via_gmail(HUMAN_AGENT_EMAIL, subject, body)
                            
                        if ok:
                            send_whatsapp_message(sender_number, "A human agent has been notified. They will contact you shortly.")
                        else:
                            send_whatsapp_message(sender_number, "I could not notify a human agent right now. Please try again later.")
                    else:
                        logger.warning("No Gmail OAuth2 or SMTP credentials found – using fallback message")
                        fallback = (
                            "Our human support team has been notified of your request.\n\n"
                            f"You can also reach us directly at:\n📧 {HUMAN_AGENT_EMAIL}\n\n"
                            "We will get back to you as soon as possible!"
                        )
                        send_whatsapp_message(sender_number, fallback)
                    pending_choice.pop(sender_number, None)

                elif state == "awaiting_choice":
                    send_whatsapp_message(sender_number, "Please reply with 1 for Chatbot or 2 for Human. You can also type Chatbot or Human.")

                # New greeting: offer options
                elif is_greeting(user_text):
                    pending_choice[sender_number] = "awaiting_choice"
                    send_whatsapp_message(sender_number, "Hi there. You want to talk to human or Chatbot? Reply 1 for Chatbot or 2 for Human. You can also type Chatbot or Human.")

                else:
                    # Default: forward to chat model
                    bot_reply = get_chat_response(sender_number, user_text)

                    print(f"🤖 Zara replies: {bot_reply}")
                    print(f"=======================================================\n")
                    logger.info(f"🤖 Zara replies: {bot_reply}")

                    send_whatsapp_message(sender_number, bot_reply)

                    # If an order was placed successfully, email the order ID to support.
                    if is_successful_order_placement(bot_reply):
                        order_id = extract_order_id(bot_reply)
                        use_gmail_api = bool(CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN)
                        use_smtp = bool(GMAIL_USER and GMAIL_APP_PASSWORD)

                        if use_gmail_api or use_smtp:
                            subject = f"[NEW ORDER] Confirmation - {order_id}"
                            body = (
                                "Dear Support Team,\n\n"
                                "A new customer order has been placed successfully through the WhatsApp assistant.\n\n"
                                f"Order ID: {order_id}\n"
                                f"Customer Phone: {sender_number}\n"
                                f"Customer Message: {user_text}\n"
                                f"Assistant Reply: {bot_reply}\n\n"
                                "Please process this order in the operations workflow.\n\n"
                                "Regards,\n"
                                "AutoServe - Order Notification Service"
                            )

                            if use_gmail_api:
                                email_ok = send_email_via_gmail_api(HUMAN_AGENT_EMAIL, subject, body)
                            else:
                                email_ok = send_email_via_gmail(HUMAN_AGENT_EMAIL, subject, body)

                            if email_ok:
                                logger.info(f"✅ Order confirmation email sent for {order_id}")
                            else:
                                logger.warning(f"⚠️ Failed to send order confirmation email for {order_id}")
                        else:
                            logger.warning("⚠️ No email configuration found for order confirmation notification")
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
    url = f"https://graph.facebook.com/v25.0/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {VERIFY_TOKEN}",
        "Content-Type": "application/json"
    }

    # WhatsApp text body limit is 4096 chars; keep margin to avoid edge-case failures.
    def split_message(message: str, max_len: int = 3900) -> list[str]:
        if len(message) <= max_len:
            return [message]

        chunks: list[str] = []
        remaining = message
        while len(remaining) > max_len:
            cut = remaining.rfind("\n", 0, max_len)
            if cut == -1:
                cut = max_len
            chunk = remaining[:cut].strip()
            if chunk:
                chunks.append(chunk)
            remaining = remaining[cut:].lstrip("\n")

        if remaining.strip():
            chunks.append(remaining.strip())

        return chunks


    try:
        parts = split_message(text or "")
        results = []

        for i, part in enumerate(parts, start=1):
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {
                    "preview_url": False,
                    "body": part
                }
            }

            res = requests.post(url, headers=headers, json=payload, timeout=10)
            logger.info(f"📤 Reply part {i}/{len(parts)} sent to {to} → Status: {res.status_code}")
            if res.status_code != 200:
                logger.error(f"❌ Failed part {i}/{len(parts)}: {res.text}")

            try:
                results.append(res.json())
            except ValueError:
                results.append({"status_code": res.status_code, "text": res.text})

        return {"parts": len(parts), "results": results}

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