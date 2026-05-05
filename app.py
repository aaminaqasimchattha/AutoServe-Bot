from fastapi import FastAPI, Request, Response, Query
import requests
import certifi
import os
import logging
import hmac
import hashlib
import json
import sys
import re
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from typing import Optional
from fastapi import UploadFile, File, HTTPException
from upload_to_pinecone import process_uploaded_file, process_uploaded_url
try:
    import psycopg2
    from psycopg2 import sql
except Exception:
    psycopg2 = None
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ── Tesseract path (Windows) ──────────────────────────────────────────────────
def _configure_tesseract():
    common_exes = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Tesseract-OCR\tesseract.exe",
    ]
    for exe in common_exes:
        try:
            if Path(exe).exists():
                pytesseract.pytesseract.tesseract_cmd = str(exe)
                tessdata_dir = Path(exe).parent / "tessdata"
                if tessdata_dir.exists():
                    os.environ.setdefault("TESSDATA_PREFIX", str(tessdata_dir) + os.sep)
                logger.info(f"Using Tesseract executable: {exe}")
                return
        except Exception:
            continue
    logger.warning("Tesseract executable not found in common locations. OCR will be disabled until configured.")

_configure_tesseract()

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
        initialize_model  = chat_model_module.initialize_model
    else:
        raise ImportError("Could not load chat model module spec")
except Exception as e:
    logger.error(f"Model import failed: {e}")

    def get_chat_response(_sender_number: str, _msg: str) -> str:
        return "Model loading failed. Please try again later."

    def initialize_model() -> bool:
        return False

load_dotenv()

GMAIL_USER         = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
HUMAN_AGENT_EMAIL  = os.getenv("HUMAN_AGENT_EMAIL") or "kashifabdulbasit@gmail.com"
CLIENT_ID          = os.getenv("CLIENT_ID")
CLIENT_SECRET      = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN      = os.getenv("REFRESH_TOKEN")

pending_choice = {}

app = FastAPI(title="WhatsApp Bot")

UPLOAD_DIR        = Path(__file__).parent / "uploads"
UPLOAD_INDEX_FILE = UPLOAD_DIR / "upload_index.json"
URL_INDEX_FILE    = UPLOAD_DIR / "url_index.json"
FRONTEND_API_URL  = os.getenv("FRONTEND_API_URL") or os.getenv("FRONTEND_URL") or "http://localhost:3000"


def _ensure_postgres_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transaction_data (
            id serial PRIMARY KEY,
            transaction_id varchar(128),
            sender_name text,
            receiver_name text,
            amount text,
            date text,
            time text,
            bank_or_service text,
            status text,
            raw_text text,
            sender_number text,
            saved_at timestamptz DEFAULT now()
        )
        """
    )
    conn.commit()


def save_transaction_record(fields: dict, raw_text: str, sender_number: str) -> Optional[int]:
    payload = {
        "transaction_id": fields.get("transaction_id"),
        "sender_name":    fields.get("sender_name"),
        "receiver_name":  fields.get("receiver_name"),
        "amount":         fields.get("amount"),
        "date":           fields.get("date"),
        "time":           fields.get("time"),
        "bank_or_service":fields.get("bank_or_service"),
        "status":         fields.get("status"),
        "raw_text":       raw_text,
        "sender_number":  sender_number,
    }
    try:
        response = requests.post(
            f"{FRONTEND_API_URL.rstrip('/')}/api/save-transaction",
            json=payload, timeout=15, verify=certifi.where(),
        )
        if not response.ok:
            logger.warning(f"Frontend transaction save API failed: {response.status_code} {response.text}")
            return None
        response_data = response.json()
        inserted_id   = response_data.get("id")
        if inserted_id is None and isinstance(response_data.get("inserted"), list) and response_data["inserted"]:
            first_row   = response_data["inserted"][0]
            inserted_id = first_row.get("id") if isinstance(first_row, dict) else None
        return int(inserted_id) if inserted_id is not None else None
    except Exception as error:
        logger.warning(f"Failed to save transaction via frontend API: {error}")
        return None


def _ensure_upload_dir() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _read_json_list(path: Path) -> list:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _append_json_record(path: Path, record: dict) -> None:
    _ensure_upload_dir()
    existing = _read_json_list(path)
    existing.append(record)
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name")
    try:
        logger.info(f"Upload started: filename={file.filename}, content_type={file.content_type}")
        _ensure_upload_dir()
        safe_name  = Path(file.filename).name
        saved_path = UPLOAD_DIR / f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"
        contents   = await file.read()
        saved_path.write_bytes(contents)
        logger.info(f"Saved file to {saved_path} ({len(contents)} bytes)")
        record = {
            "filename":     safe_name,
            "saved_path":   str(saved_path),
            "size":         len(contents),
            "content_type": file.content_type,
            "saved_at":     datetime.now().isoformat(),
        }
        _append_json_record(UPLOAD_INDEX_FILE, record)
        try:
            pinecone_result = process_uploaded_file(saved_path, source_name=safe_name)
            logger.info(
                f"Embedding pipeline complete for {safe_name}: "
                f"rows_processed={pinecone_result.get('rows_processed', 0)}, "
                f"vectors_upserted={pinecone_result.get('vectors_upserted', 0)}"
            )
        except Exception as e:
            logger.warning(f"Pinecone processing failed for {safe_name}: {str(e)}")
            pinecone_result = {"rows_processed": 0, "vectors_upserted": 0, "error": "Vector storage temporarily unavailable"}
        return {
            "success":          True,
            "message":          "File uploaded successfully" + (" (vector storage unavailable)" if pinecone_result.get("error") else ""),
            "rows_processed":   pinecone_result.get("rows_processed", 0),
            "vectors_upserted": pinecone_result.get("vectors_upserted", 0),
            "file":             record,
        }
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/api/upload-urls")
async def api_upload_urls(request: Request):
    payload = await request.json()
    url     = str(payload.get("url") or "").strip()
    domain  = str(payload.get("domain") or "").strip()
    if not url:
        return Response(
            content=json.dumps({"success": False, "message": "Missing url"}),
            status_code=400, media_type="application/json",
        )
    try:
        record = {"url": url, "domain": domain or url, "saved_at": datetime.now().isoformat()}
        _append_json_record(URL_INDEX_FILE, record)
        try:
            pinecone_result = process_uploaded_url(url, domain or url)
        except Exception as e:
            logger.warning(f"Pinecone processing failed for URL {url}: {str(e)}")
            pinecone_result = {"rows_processed": 1, "vectors_upserted": 0, "error": "Vector storage temporarily unavailable"}
        return {
            "success":          True,
            "message":          "URL uploaded successfully" + (" (vector storage unavailable)" if pinecone_result.get("error") else ""),
            "vectors_upserted": pinecone_result.get("vectors_upserted", 0),
            "url":              record,
        }
    except Exception as e:
        logger.error(f"URL upload failed: {str(e)}")
        return Response(
            content=json.dumps({"success": False, "message": f"Upload failed: {str(e)}"}),
            status_code=500, media_type="application/json",
        )


def get_gmail_access_token() -> Optional[str]:
    global REFRESH_TOKEN
    if not CLIENT_ID or not CLIENT_SECRET or not REFRESH_TOKEN:
        return None
    try:
        res = requests.post(
            "https://oauth2.googleapis.com/token",
            data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                  "refresh_token": REFRESH_TOKEN, "grant_type": "refresh_token"},
            verify=certifi.where()
        )
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
    message            = MIMEText(body)
    message["To"]      = to_email
    message["Subject"] = subject
    raw_message        = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    try:
        res = requests.post(
            "https://www.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"raw": raw_message}, verify=certifi.where()
        )
        if res.status_code == 200:
            logger.info("Email sent via Gmail API successfully!")
            return True
        logger.error(f"Error sending email via Gmail API: {res.text}")
        return False
    except Exception as e:
        logger.error(f"Exception sending email via Gmail API: {e}")
        return False


def send_email_via_smtp(to_email: str, subject: str, body: str) -> bool:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or not to_email:
        logger.warning("Gmail sender, app password, or destination email not set")
        return False
    message            = MIMEText(body)
    message["From"]    = GMAIL_USER
    message["To"]      = to_email
    message["Subject"] = subject
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(message)
        logger.info("Gmail SMTP notification sent successfully")
        return True
    except Exception as e:
        logger.error(f"Error sending email via Gmail SMTP: {e}")
        return False


def send_transaction_summary_email(fields: dict, raw_text: str, sender_number: str, row_id: Optional[int] = None) -> bool:
    use_gmail_api = bool(CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN)
    use_smtp      = bool(GMAIL_USER and GMAIL_APP_PASSWORD)
    if not (use_gmail_api or use_smtp):
        logger.warning("No email configuration found for transaction notification")
        return False
    reference = fields.get("transaction_id") or (f"TX-{row_id}" if row_id is not None else "N/A")
    subject   = f"[NEW TRANSACTION] Confirmation - {reference}"
    body      = (
        "Dear Support Team,\n\n"
        "A new transaction was extracted and saved successfully.\n\n"
        f"Reference:        {reference}\n"
        f"Database Row ID:   {row_id if row_id is not None else 'N/A'}\n"
        f"Customer Phone:    {sender_number}\n"
        f"Sender Name:       {fields.get('sender_name') or 'Not found'}\n"
        f"Receiver Name:     {fields.get('receiver_name') or 'Not found'}\n"
        f"Amount:            {fields.get('amount') or 'Not found'}\n"
        f"Date:              {fields.get('date') or 'Not found'}\n"
        f"Time:              {fields.get('time') or 'Not found'}\n"
        f"Bank/Service:      {fields.get('bank_or_service') or 'Not found'}\n"
        f"Status:            {fields.get('status') or 'Not found'}\n\n"
        "OCR Text Preview:\n"
        f"{(raw_text or '')[:1500]}\n\n"
        "Please review this transaction in the operations workflow.\n\n"
        "Regards,\nAutoServe - Transaction Notification Service"
    )
    if use_gmail_api:
        return send_email_via_gmail_api(HUMAN_AGENT_EMAIL, subject, body)
    return send_email_via_smtp(HUMAN_AGENT_EMAIL, subject, body)


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
        "&access_type=offline&prompt=consent&response_type=code"
        f"&redirect_uri={redirect_uri}&client_id={CLIENT_ID}"
    )
    return {
        "instructions": (
            "1. Ensure the redirect_uri below is added to your Google Developer Console "
            "under Authorized redirect URIs for your Client ID.\n"
            f"Authorized Redirect URI: {redirect_uri}\n"
            "2. Open the authorization_url to log in and authorize the Gmail sending scope."
        ),
        "redirect_uri":      redirect_uri,
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
    try:
        res        = requests.post(
            "https://oauth2.googleapis.com/token",
            data={"code": code, "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                  "redirect_uri": redirect_uri, "grant_type": "authorization_code"},
            verify=certifi.where()
        )
        token_data = res.json()
        if "refresh_token" in token_data:
            refresh_token   = token_data["refresh_token"]
            env_path        = Path(__file__).parent / ".env"
            env_content     = env_path.read_text(encoding="utf-8")
            lines           = [l for l in env_content.splitlines() if not l.strip().startswith("REFRESH_TOKEN=")]
            lines.append(f"REFRESH_TOKEN={refresh_token}")
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            REFRESH_TOKEN               = refresh_token
            os.environ["REFRESH_TOKEN"] = refresh_token
            return {"status": "success", "message": "Gmail OAuth refresh token has been saved to your .env file and loaded in memory!"}
        return {"error": "Failed to obtain refresh token", "google_response": token_data}
    except Exception as e:
        return {"error": f"Error during token exchange: {str(e)}"}


# ─── CONFIG ───────────────────────────────────────────────────────────────────
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_ID     = os.getenv("PHONE_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
APP_SECRET   = os.getenv("APP_SECRET")

if not all([ACCESS_TOKEN, PHONE_ID, VERIFY_TOKEN]):
    logger.error("❌ Missing environment variables!")
    logger.error(f"  ACCESS_TOKEN: {'✓' if ACCESS_TOKEN else '✗ MISSING'}")
    logger.error(f"  PHONE_ID:     {'✓' if PHONE_ID     else '✗ MISSING'}")
    logger.error(f"  VERIFY_TOKEN: {'✓' if VERIFY_TOKEN else '✗ MISSING'}")
    logger.error(f"  APP_SECRET:   {'✓' if APP_SECRET   else '✗ MISSING'}")
else:
    logger.info("✅ All environment variables loaded!")
    logger.info(f"   PHONE_ID:          {PHONE_ID}")
    logger.info(f"   VERIFY_TOKEN:      {VERIFY_TOKEN}")
    logger.info(f"   APP_SECRET loaded: {'✓' if APP_SECRET else '✗ NOT SET'}")


# ─── IMAGE / OCR HELPERS ──────────────────────────────────────────────────────

def download_whatsapp_image(media_id: str) -> Image.Image:
    url_res = requests.get(
        f"https://graph.facebook.com/v18.0/{media_id}",
        headers={"Authorization": f"Bearer {VERIFY_TOKEN}"},
        verify=certifi.where()
    )
    if url_res.status_code != 200:
        raise Exception(f"Media URL fetch failed: {url_res.text}")
    media_url = url_res.json().get("url")
    if not media_url:
        raise Exception("No media URL in response")
    img_res = requests.get(
        media_url,
        headers={"Authorization": f"Bearer {VERIFY_TOKEN}"},
        verify=certifi.where()
    )
    if img_res.status_code != 200:
        raise Exception(f"Image download failed: {img_res.text}")
    return Image.open(BytesIO(img_res.content))


def preprocess_and_ocr(img: Image.Image) -> str:
    try:
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        if w < 1000:
            scale           = 1000 / w
            resample_filter = getattr(Image, 'LANCZOS', 3) if not hasattr(Image, 'Resampling') else Image.Resampling.LANCZOS
            img             = img.resize((int(w * scale), int(h * scale)), resample_filter)
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = img.convert("L")
        return pytesseract.image_to_string(img, config="--psm 6 --oem 3")
    except Exception as e:
        logger.warning(f"⚠ OCR processing skipped: {str(e)}")
        return "[Image received - OCR not available. To enable OCR, install Tesseract-OCR from https://github.com/UB-Mannheim/tesseract/wiki]"


def extract_transaction_fields(text: str) -> dict[str, str | None]:
    result: dict[str, str | None] = {
        "transaction_id":  None,
        "sender_name":     None,
        "receiver_name":   None,
        "amount":          None,
        "date":            None,
        "time":            None,
        "bank_or_service": None,
        "status":          None,
    }

    for pattern in [
        r"(?:Transaction\s*ID|TXN|Ref\s*No|Reference|Trace\s*No|RRN)[:\s#]*([A-Z0-9\-]{6,30})",
        r"\b(TXN[A-Z0-9]{6,25})\b",
        r"\b([A-Z]{2,4}[0-9]{8,20})\b",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            result["transaction_id"] = m.group(1).strip()
            break

    m = re.search(
        r"(?:From|Sender|Paid\s*by|Account\s*Holder|Debit\s*Account\s*Title)[:\s]+([A-Za-z\s]{3,40})",
        text, re.IGNORECASE
    )
    if m:
        result["sender_name"] = m.group(1).strip()

    m = re.search(
        r"(?:To|Receiver|Recipient|Beneficiary|Credit\s*Account\s*Title|Paid\s*to)[:\s]+([A-Za-z\s]{3,40})",
        text, re.IGNORECASE
    )
    if m:
        result["receiver_name"] = m.group(1).strip()

    m = re.search(r"(?:Rs\.?|PKR|Amount)[:\s]*([\d,]+(?:\.\d{1,2})?)", text, re.IGNORECASE)
    if m:
        result["amount"] = f"Rs. {m.group(1).strip()}"

    m = re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})", text)
    if m:
        result["date"] = m.group(1).strip()

    m = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?)", text, re.IGNORECASE)
    if m:
        result["time"] = m.group(1).strip()

    for name, pattern in {
        "Easypaisa":    r"easypaisa",
        "JazzCash":     r"jazzcash",
        "HBL":          r"\bHBL\b|Habib\s*Bank",
        "UBL":          r"\bUBL\b|United\s*Bank",
        "Meezan":       r"meezan",
        "Allied Bank":  r"allied\s*bank",
        "MCB":          r"\bMCB\b",
        "Bank Alfalah": r"alfalah",
        "Sadapay":      r"sadapay",
        "Nayapay":      r"nayapay",
    }.items():
        if re.search(pattern, text, re.IGNORECASE):
            result["bank_or_service"] = name
            break

    for status, pattern in {
        "Successful": r"success(?:ful)?|completed|approved",
        "Failed":     r"fail(?:ed)?|declined|rejected",
        "Pending":    r"pending|processing",
    }.items():
        if re.search(pattern, text, re.IGNORECASE):
            result["status"] = status
            break

    return result


def format_transaction_message(fields: dict) -> str:
    lines   = ["✅ *Transaction Details Extracted*\n"]
    mapping = {
        "transaction_id":  "🔢 Transaction ID",
        "sender_name":     "👤 Sender",
        "receiver_name":   "👤 Receiver",
        "amount":          "💰 Amount",
        "date":            "📅 Date",
        "time":            "🕐 Time",
        "bank_or_service": "🏦 Bank/Service",
        "status":          "📊 Status",
    }
    for key, label in mapping.items():
        value = fields.get(key) or "Not found"
        lines.append(f"{label}: {value}")
    return "\n".join(lines)


# ─── STARTUP ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    logger.info("Starting WhatsApp bot...")
    initialize_model()
    logger.info("Startup complete")


# ─── HEALTH / DEBUG ───────────────────────────────────────────────────────────

@app.get("/")
async def health_check():
    return {
        "status": "Bot is running ✓",
        "environment": {
            "ACCESS_TOKEN": "✓" if ACCESS_TOKEN else "✗ MISSING",
            "PHONE_ID":     "✓" if PHONE_ID     else "✗ MISSING",
            "VERIFY_TOKEN": "✓" if VERIFY_TOKEN else "✗ MISSING",
            "APP_SECRET":   "✓" if APP_SECRET   else "✗ NOT SET",
        }
    }


@app.get("/webhook/test")
async def webhook_test():
    return {"status": "ok", "message": "Webhook test endpoint is working."}


@app.get("/debug")
async def debug():
    return {
        "message":          "Debug endpoint",
        "ACCESS_TOKEN_set": bool(ACCESS_TOKEN),
        "PHONE_ID_set":     bool(PHONE_ID),
        "VERIFY_TOKEN_set": bool(VERIFY_TOKEN),
        "webhook_url":      "/webhook/whatsapp/webhook"
    }


# ─── WEBHOOK VERIFICATION ─────────────────────────────────────────────────────

@app.get("/webhook/Whatsapp/webhook")
async def verify(
    hub_mode:         Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge:    Optional[str] = Query(None, alias="hub.challenge")
):
    logger.info(f"🔐 Verification: mode={hub_mode}, token={hub_verify_token}, challenge={hub_challenge}")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully!")
        return Response(content=hub_challenge or "", media_type="text/plain")
    logger.warning("❌ Webhook verification failed")
    return Response(content="Forbidden", status_code=403)


# ─── DEDUP ────────────────────────────────────────────────────────────────────
processed_message_ids = set()


# ─── HELPERS (defined at module level so they can be reused) ──────────────────

def is_greeting(s: str) -> bool:
    words = ["hi", "hello", "hey", "hiya", "greetings"]
    txt   = (s or "").strip().lower()
    for w in words:
        if txt == w or txt.startswith(w + " ") or (" " + w + " ") in (" " + txt + " "):
            return True
    return False


def is_human_request(s: str) -> bool:
    """
    Returns True only when the user is NOT in a payment flow.
    Note: the caller must guard this with state checks first —
    never call this when state == 'awaiting_payment_method'.
    """
    txt      = (s or "").strip().lower()
    patterns = [
        "i want to talk to human", "want to talk to human",
        "talk to human", "human agent", "connect me to human",
        "connect me to a human", "live agent", "real person",
        "support agent", "human support",
    ]
    # "2" is intentionally NOT in this list anymore — it's ambiguous
    # (could be payment choice). We handle plain "2" via the menu state only.
    if txt in ("human", "agent", "support", "type two", "option 2"):
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
    """
    FIX: expanded keyword list so AI replies like
    'Your order has been placed!' still trigger the payment prompt.
    """
    txt = (reply_text or "").lower()
    order_keywords = [
        "order placed",
        "order has been placed",
        "order was placed",
        "successfully placed",
        "success: order placed",
        "order confirmed",
        "order has been confirmed",
    ]
    has_keyword  = any(kw in txt for kw in order_keywords)
    has_order_id = bool(extract_order_id(reply_text))
    logger.info(f"🔍 Order check → has_keyword={has_keyword}, has_order_id={has_order_id}, text_preview={txt[:80]!r}")
    return has_keyword and has_order_id


def send_payment_buttons(sender_number: str) -> None:
    """Send a plain-text payment prompt right after order placement."""
    send_whatsapp_message(
        sender_number,
        "Your order has been placed successfully.\n\nPlease choose a payment method:\n\n1) Cash on Delivery\n2) Pay through any banking app\n\nReply with 1 or 2.\nIf you choose bank app, please send a screenshot of the transaction for order confirmation."
    )

def _send_order_email(order_id: str, sender_number: str, user_text: str, bot_reply: str) -> None:
    use_gmail_api = bool(CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN)
    use_smtp      = bool(GMAIL_USER and GMAIL_APP_PASSWORD)
    if not (use_gmail_api or use_smtp):
        logger.warning("⚠️ No email configuration found for order confirmation")
        return
    subject = f"[NEW ORDER] Confirmation - {order_id}"
    body    = (
        "Dear Support Team,\n\n"
        "A new customer order has been placed successfully through the WhatsApp assistant.\n\n"
        f"Order ID:         {order_id}\n"
        f"Customer Phone:   {sender_number}\n"
        f"Customer Message: {user_text}\n"
        f"Assistant Reply:  {bot_reply}\n\n"
        "Please process this order in the operations workflow.\n\n"
        "Regards,\nAutoServe - Order Notification Service"
    )
    ok = send_email_via_gmail_api(HUMAN_AGENT_EMAIL, subject, body) if use_gmail_api \
         else send_email_via_smtp(HUMAN_AGENT_EMAIL, subject, body)
    if ok:
        logger.info(f"✅ Order confirmation email sent for {order_id}")
    else:
        logger.warning(f"⚠️ Failed to send order confirmation email for {order_id}")


def _send_human_agent_email(sender_number: str, user_text: str) -> bool:
    use_gmail_api = bool(CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN)
    use_smtp      = bool(GMAIL_USER and GMAIL_APP_PASSWORD)
    if not (use_gmail_api or use_smtp):
        return False
    subject = f"Human Agent Requested - {sender_number}"
    body    = (
        "═══════════════════════════════════════════════════════\n"
        "                   AUTOSERVE - SUPPORT ALERT\n"
        "═══════════════════════════════════════════════════════\n\n"
        "A customer has requested to speak with a human agent.\n\n"
        "─────────────────────────────────────────────────────\n"
        "CUSTOMER DETAILS:\n"
        "─────────────────────────────────────────────────────\n"
        f"Phone Number:    {sender_number}\n"
        f"Contact Method:  WhatsApp\n"
        f"Request Time:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
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
    return send_email_via_gmail_api(HUMAN_AGENT_EMAIL, subject, body) if use_gmail_api \
           else send_email_via_smtp(HUMAN_AGENT_EMAIL, subject, body)


# ─── MAIN WEBHOOK ─────────────────────────────────────────────────────────────

@app.post("/webhook/Whatsapp/webhook")
async def webhook(request: Request):
    global processed_message_ids
    try:
        headers = dict(request.headers)
        body    = await request.body()

        if not body:
            logger.warning("⚠️ Empty request body")
            return {"status": "ok"}

        # ── Signature verification ────────────────────────────────────────────
        if APP_SECRET:
            signature_header = headers.get("x-hub-signature-256")
            if not signature_header or not signature_header.startswith("sha256="):
                logger.warning("❌ Missing or invalid X-Hub-Signature-256 header")
                return Response(content="Missing or invalid signature", status_code=403)
            received_signature = signature_header.split("=", 1)[1]
            expected_signature = hmac.new(
                APP_SECRET.encode("utf-8"), body, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(received_signature, expected_signature):
                logger.warning("❌ Webhook signature mismatch")
                return Response(content="Invalid signature", status_code=403)
            logger.info("✅ Webhook signature verified")
        else:
            logger.warning("⚠️ APP_SECRET not set — skipping signature verification")

        data    = await request.json()
        entry   = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value   = changes.get("value", {})

        if "statuses" in value:
            return {"status": "ok"}

        messages = value.get("messages", [])
        if not messages:
            return {"status": "ok"}

        message       = messages[0]
        message_id    = message.get("id")
        sender_number = message.get("from")
        message_type  = message.get("type")

        if message_id and message_id in processed_message_ids:
            logger.info(f"🔄 Duplicate message {message_id}, skipping.")
            return {"status": "ok"}
        if message_id:
            processed_message_ids.add(message_id)

        # ══════════════════════════════════════════════════════════════════════
        # TEXT MESSAGE
        # ══════════════════════════════════════════════════════════════════════
        if message_type == "text":
            user_text = message.get("text", {}).get("body", "")
            logger.info(f"💬 User {sender_number} says: {user_text!r}")

            txt_lower = user_text.strip().lower()
            state     = pending_choice.get(sender_number)

            logger.info(f"📌 State for {sender_number}: {state!r}")

            # ── State: awaiting PAID reply after bank transfer ────────────────
            if state == "awaiting_bank_paid":
                paid_txt = txt_lower.strip()
                if paid_txt in ("paid", "i paid", "done", "payment done", "completed"):
                    send_whatsapp_message(
                        sender_number,
                        "✅ Thank you for choosing Banking App. Please send a screenshot of the transaction for order confirmation."
                    )
                    try:
                        requests.post(
                            f"{FRONTEND_API_URL.rstrip('/')}/api/save-payment-method",
                            json={"phone": sender_number, "payment_method": "Bank App", "status": "paid"},
                            timeout=8, verify=certifi.where()
                        )
                    except Exception:
                        pass
                    pending_choice.pop(sender_number, None)
                else:
                    send_whatsapp_message(
                        sender_number,
                        "⏳ Please send a screenshot of the bank transaction for order confirmation."
                    )
                return {"status": "ok"}

            # ══════════════════════════════════════════════════════════════════
            # MAIN MENU SHORTCUTS
            # Payment is now handled via interactive buttons (message_type ==
            # 'interactive') — no text-based state machine needed here.
            # ══════════════════════════════════════════════════════════════════

            # ── Option 1 / Chatbot ────────────────────────────────────────────
            if txt_lower in ("1", "chatbot", "bot", "ai", "type one", "option 1"):
                pending_choice.pop(sender_number, None)
                send_whatsapp_message(sender_number, "Hi there, I'm Zara, the AI Assistant. How can I help you?")
                logger.info(f"✅ Sent chatbot greeting to {sender_number}")
                return {"status": "ok"}

            # ── Option 2 / Human agent ────────────────────────────────────────
            # Note: plain "2" is no longer treated as human request here because
            # it would conflict with payment method selection. Users who want a
            # human agent from the main menu can still type "2" when the greeting
            # menu is active (state == awaiting_choice handled below).
            if is_human_request(user_text):
                ok = _send_human_agent_email(sender_number, user_text)
                if ok:
                    send_whatsapp_message(sender_number, "A human agent has been notified. They will contact you shortly.")
                else:
                    if HUMAN_AGENT_EMAIL:
                        send_whatsapp_message(
                            sender_number,
                            f"Our human support team has been notified.\n\n"
                            f"You can also reach us at:\n📧 {HUMAN_AGENT_EMAIL}\n\nWe'll be in touch soon!"
                        )
                    else:
                        send_whatsapp_message(sender_number, "I could not notify a human agent right now. Please try again later.")
                pending_choice.pop(sender_number, None)
                logger.info(f"✅ Human agent request processed for {sender_number}")
                return {"status": "ok"}

            # ── State: awaiting initial menu choice ───────────────────────────
            if state == "awaiting_choice":
                if txt_lower == "2":
                    # "2" in the main menu means human agent
                    ok = _send_human_agent_email(sender_number, user_text)
                    if ok:
                        send_whatsapp_message(sender_number, "A human agent has been notified. They will contact you shortly.")
                    else:
                        send_whatsapp_message(
                            sender_number,
                            f"Our human support team has been notified.\n\n"
                            f"You can also reach us at:\n📧 {HUMAN_AGENT_EMAIL}\n\nWe'll be in touch soon!"
                        )
                    pending_choice.pop(sender_number, None)
                else:
                    send_whatsapp_message(
                        sender_number,
                        "Please reply with *1* for Chatbot or *2* for Human. You can also type *Chatbot* or *Human*."
                    )
                return {"status": "ok"}

            # ── Greeting ──────────────────────────────────────────────────────
            if is_greeting(user_text):
                pending_choice[sender_number] = "awaiting_choice"
                send_whatsapp_message(
                    sender_number,
                    "Hi there! 👋 Would you like to talk to:\n\n"
                    "1️⃣ *Chatbot* (AI Assistant)\n"
                    "2️⃣ *Human Agent*\n\n"
                    "Reply with *1* or *2*, or type *Chatbot* / *Human*."
                )
                logger.info(f"👋 Sent greeting menu to {sender_number}")
                return {"status": "ok"}

            # ── Default: AI chat ──────────────────────────────────────────────
            bot_reply = get_chat_response(sender_number, user_text)
            logger.info(f"🤖 Zara replies: {bot_reply!r}")
            send_whatsapp_message(sender_number, bot_reply)

            # Check if an order was just placed and trigger payment flow
            if is_successful_order_placement(bot_reply):
                order_id = extract_order_id(bot_reply)
                logger.info(f"🛒 Order detected: {order_id}")
                _send_order_email(order_id, sender_number, user_text, bot_reply)
                send_payment_buttons(sender_number)

        # ══════════════════════════════════════════════════════════════════════
        # INTERACTIVE MESSAGE — button replies (payment method selection)
        # ══════════════════════════════════════════════════════════════════════
        elif message_type == "interactive":
            btn_id = (
                message.get("interactive", {})
                        .get("button_reply", {})
                        .get("id", "")
                        .lower()
            )
            logger.info(f"🔘 Interactive button pressed by {sender_number}: {btn_id!r}")

            if btn_id == "cod":
                send_whatsapp_message(
                    sender_number,
                    "✅ Thank you for choosing Cash on Delivery. Your order will be processed shortly. 🎉"
                )
                try:
                    requests.post(
                        f"{FRONTEND_API_URL.rstrip('/')}/api/save-payment-method",
                        json={"phone": sender_number, "payment_method": "Cash on Delivery"},
                        timeout=8, verify=certifi.where()
                    )
                except Exception:
                    pass

            elif btn_id == "bank_app":
                acct = "0088765789758"
                send_whatsapp_message(
                    sender_number,
                    f"✅ Thank you for choosing Banking App.\n\nPlease transfer the payment to:\n\n*Account: {acct}*\n\nAfter payment, send a screenshot of the transaction for order confirmation."
                )
                pending_choice[sender_number] = "awaiting_bank_paid"
                try:
                    requests.post(
                        f"{FRONTEND_API_URL.rstrip('/')}/api/save-payment-method",
                        json={"phone": sender_number, "payment_method": "Bank App",
                              "account_number": acct, "status": "initiated"},
                        timeout=8, verify=certifi.where()
                    )
                except Exception:
                    pass

            else:
                logger.warning(f"⚠️ Unknown button id: {btn_id!r}")

        # ══════════════════════════════════════════════════════════════════════
        # IMAGE MESSAGE — transaction screenshot OCR + email notification
        # ══════════════════════════════════════════════════════════════════════
        elif message_type == "image":
            media_id = message.get("image", {}).get("id")
            if not media_id:
                send_whatsapp_message(sender_number, "❌ Could not read image. Please try again.")
            else:
                if pending_choice.get(sender_number) == "awaiting_bank_paid":
                    send_whatsapp_message(
                        sender_number,
                        "✅ Screenshot received. Thank you for choosing Banking App. Your payment confirmation is being checked now."
                    )
                    try:
                        requests.post(
                            f"{FRONTEND_API_URL.rstrip('/')}/api/save-payment-method",
                            json={"phone": sender_number, "payment_method": "Bank App", "status": "screenshot_received"},
                            timeout=8, verify=certifi.where()
                        )
                    except Exception:
                        pass
                    pending_choice.pop(sender_number, None)
                else:
                    send_whatsapp_message(sender_number, "⏳ Processing your transaction image...")
                    try:
                        img      = download_whatsapp_image(media_id)
                        raw_text = preprocess_and_ocr(img)
                        logger.info(f"📝 OCR text: {raw_text[:300]}")

                        if not raw_text.strip():
                            send_whatsapp_message(
                                sender_number,
                                "❌ Could not read text from image. Please send a clearer screenshot."
                            )
                        else:
                            fields = extract_transaction_fields(raw_text)
                            logger.info(f"✅ Fields extracted: {fields}")

                            try:
                                row_id = save_transaction_record(fields, raw_text, sender_number)
                                logger.info(f"✅ Saved transaction record id={row_id}")
                                email_ok = send_transaction_summary_email(fields, raw_text, sender_number, row_id=row_id)
                                if email_ok:
                                    logger.info(f"✅ Transaction summary email sent for {fields.get('transaction_id') or row_id}")
                                else:
                                    logger.warning(f"⚠️ Transaction summary email not sent for {fields.get('transaction_id') or row_id}")
                            except Exception as e:
                                logger.warning(f"⚠️ Failed to save transaction record: {e}")

                            send_whatsapp_message(
                                sender_number,
                                f"✅ Your transaction screenshot was received.\n\nExtracted reference: {fields.get('transaction_id') or 'Not found'}"
                            )
                            send_whatsapp_message(sender_number, format_transaction_message(fields))
                    except Exception as e:
                        logger.error(f"❌ Image processing failed: {e}", exc_info=True)
                        send_whatsapp_message(
                            sender_number,
                            "❌ Something went wrong processing your image. Please try again."
                        )

        # ══════════════════════════════════════════════════════════════════════
        else:
            if pending_choice.get(sender_number) == "awaiting_bank_paid":
                send_whatsapp_message(
                    sender_number,
                    "⏳ Please send a screenshot of the bank transaction for order confirmation."
                )
            else:
                logger.info(f"📦 Unsupported message type: {message_type}")
                send_whatsapp_message(sender_number, "Sorry, I only support text messages and transaction images!")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


# ─── SEND WHATSAPP MESSAGE ────────────────────────────────────────────────────

def send_whatsapp_message(to: str, text: str):
    url     = f"https://graph.facebook.com/v25.0/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {VERIFY_TOKEN}",
        "Content-Type":  "application/json"
    }

    def split_message(message: str, max_len: int = 3900) -> list[str]:
        if len(message) <= max_len:
            return [message]
        chunks    = []
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
        parts   = split_message(text or "")
        results = []
        for i, part in enumerate(parts, start=1):
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type":    "individual",
                "to":                to,
                "type":              "text",
                "text":              {"preview_url": False, "body": part}
            }
            res = requests.post(url, headers=headers, json=payload, timeout=10, verify=certifi.where())
            logger.info(f"📤 Reply part {i}/{len(parts)} to {to} → {res.status_code}")
            if res.status_code != 200:
                logger.error(f"❌ Failed part {i}: {res.text}")
            try:
                results.append(res.json())
            except ValueError:
                results.append({"status_code": res.status_code, "text": res.text})
        return {"parts": len(parts), "results": results}
    except requests.exceptions.Timeout:
        logger.error("❌ Timeout sending WhatsApp message")
        return {"error": "Timeout"}
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error sending WhatsApp message: {e}")
        return {"error": str(e)}


# Terminal 1: uvicorn app:app --reload --port 8000
# Terminal 2: ngrok http 8000 --domain circling-snowfall-emission.ngrok-free.dev
# Meta Dashboard Setup:
#   - Callback URL: https://circling-snowfall-emission.ngrok-free.dev/webhook
#   - Token: your VERIFY_TOKEN from .env
#   - Check: messages event
#   - Click: Verify and Save