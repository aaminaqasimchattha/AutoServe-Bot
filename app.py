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
    # Remove cached version to force reload on server restart
    if "chat_model_module" in sys.modules:
        del sys.modules["chat_model_module"]
    spec = importlib.util.spec_from_file_location("chat_model_module", ai_agent_path / "chat_model.py")
    if spec and spec.loader:
        chat_model_module = importlib.util.module_from_spec(spec)
        sys.modules["chat_model_module"] = chat_model_module  # Register so Python tracks it
        spec.loader.exec_module(chat_model_module)
        get_chat_response = chat_model_module.get_chat_response
        initialize_model  = chat_model_module.initialize_model
    else:
        raise ImportError("Could not load chat model module spec")
except Exception as e:
    logger.error(f"Model import failed: {e}")

    def get_chat_response(_sender_number: str, _msg: str, **kwargs) -> str:
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


def _ensure_upload_dir() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _append_json_record(file_path: Path, record: dict) -> None:
    _ensure_upload_dir()
    records = []
    if file_path.exists():
        try:
            records = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(records, list):
                records = []
        except Exception:
            records = []
    records.append(record)
    file_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


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
            created_at timestamptz DEFAULT now(),
            saved_at timestamptz DEFAULT now()
        )
        """
    )
    cur.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'transaction_data'
                  AND column_name = 'created_at'
            ) THEN
                ALTER TABLE transaction_data ADD COLUMN created_at timestamptz;
            END IF;

            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'transaction_data'
                  AND column_name = 'saved_at'
            ) THEN
                UPDATE transaction_data
                SET created_at = COALESCE(created_at, saved_at, now())
                WHERE created_at IS NULL;
            ELSE
                UPDATE transaction_data
                SET created_at = COALESCE(created_at, now())
                WHERE created_at IS NULL;
            END IF;

            ALTER TABLE transaction_data ALTER COLUMN created_at SET DEFAULT now();
            ALTER TABLE transaction_data ALTER COLUMN created_at SET NOT NULL;
        EXCEPTION
            WHEN duplicate_column THEN NULL;
        END $$;
        """
    )
    conn.commit()


def _save_transaction_direct(payload: dict) -> Optional[int]:
    dsn = (os.getenv("DATABASE_URL") or os.getenv("DB_URI") or "").strip()
    if not dsn or psycopg2 is None:
        return None
    try:
        conn = psycopg2.connect(dsn)
        _ensure_postgres_table(conn)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO transaction_data (
                transaction_id, sender_name, receiver_name, amount, date, time,
                bank_or_service, status, raw_text, sender_number
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                payload.get("transaction_id"),
                payload.get("sender_name"),
                payload.get("receiver_name"),
                payload.get("amount"),
                payload.get("date"),
                payload.get("time"),
                payload.get("bank_or_service"),
                payload.get("status"),
                payload.get("raw_text"),
                payload.get("sender_number")
            )
        )
        fetched = cur.fetchone()
        inserted_id = fetched[0] if fetched else None
        conn.commit()
        conn.close()
        return inserted_id
    except Exception as e:
        logger.warning(f"Direct Postgres transaction save failed: {e}")
        return None


def save_transaction_record(fields: dict, raw_text: str, sender_number: str) -> Optional[int]:
    payload = {
        "transaction_id": fields.get("transaction_id"),
        "sender_name": fields.get("sender_name"),
        "receiver_name": fields.get("receiver_name"),
        "amount": fields.get("amount"),
        "date": fields.get("date"),
        "time": fields.get("time"),
        "bank_or_service": fields.get("bank_or_service"),
        "status": fields.get("status"),
        "raw_text": raw_text,
        "sender_number": sender_number,
    }
    
    inserted_id = None
    try:
        response = requests.post(
            f"{FRONTEND_API_URL.rstrip('/')}/api/save-transaction",
            json=payload, timeout=15, verify=certifi.where(),
        )
        if response.ok:
            response_data = response.json()
            inserted_id   = response_data.get("id")
            if inserted_id is None and isinstance(response_data.get("inserted"), list) and response_data["inserted"]:
                first_row   = response_data["inserted"][0]
                inserted_id = first_row.get("id") if isinstance(first_row, dict) else None
        else:
            logger.warning(f"Frontend transaction API failed: {response.status_code} {response.text}")
    except Exception as error:
        logger.warning(f"Failed to reach frontend API: {error}")
        
    if inserted_id is None:
        inserted_id = _save_transaction_direct(payload)
        
    return int(inserted_id) if inserted_id is not None else None


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
        logger.warning(f"Gmail API missing credentials: ID={bool(CLIENT_ID)}, Secret={bool(CLIENT_SECRET)}, Token={bool(REFRESH_TOKEN)}")
        return None
    try:
        res = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": CLIENT_ID, 
                "client_secret": CLIENT_SECRET,
                "refresh_token": REFRESH_TOKEN, 
                "grant_type": "refresh_token"
            },
            verify=certifi.where(),
            timeout=10
        )
        if res.status_code == 200:
            return res.json().get("access_token")
        else:
            logger.error(f"Gmail Token Refresh Error {res.status_code}: {res.text}")
            return None
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


def get_whatsapp_access_token() -> Optional[str]:
    if ACCESS_TOKEN:
        return ACCESS_TOKEN
    logger.error("❌ WhatsApp ACCESS_TOKEN is missing. Replies to WhatsApp messages cannot be sent.")
    return None


# ─── IMAGE / OCR HELPERS ──────────────────────────────────────────────────────

def download_whatsapp_image(media_id: str) -> Image.Image:
    """Download image from WhatsApp media API."""
    access_token = get_whatsapp_access_token()
    if not access_token:
        raise Exception("Missing WhatsApp access token")
    url_res = requests.get(
        f"https://graph.facebook.com/v18.0/{media_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        verify=certifi.where()
    )
    if url_res.status_code != 200:
        raise Exception(f"Media URL fetch failed: {url_res.text}")
    media_url = url_res.json().get("url")
    if not media_url:
        raise Exception("No media URL in response")
    img_res = requests.get(
        media_url,
        headers={"Authorization": f"Bearer {access_token}"},
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

    # ID Regex: Catch common patterns including OCR errors like '1D#' or 'ID#'
    # Look for patterns like 1D#49260509712 or ID#... or ID ...
    for pattern in [
        r"(?:Transaction\s*ID|TXN|Ref\s*No|Reference|Trace\s*No|RRN|1D#|ID#)[:\s#]*([A-Z0-9\-]{6,30})",
        r"\bID[:\s#]+([0-9]{8,25})\b",
        r"\b(TXN[A-Z0-9]{6,25})\b",
        r"\b([A-Z]{2,4}[0-9]{8,20})\b",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            result["transaction_id"] = m.group(1).strip()
            break

    # Sender Regex: Look for 'Sent by' followed by name, often ending before a phone number
    m = re.search(
        r"(?:From|Sender|Paid\s*by|Sent\s*by|Account\s*Holder|Debit\s*Account\s*Title)[:\s]+([A-Za-z\s]+?)(?:\r?\n|\s+\d{10,15}|\s*$)",
        text, re.IGNORECASE
    )
    if m:
        result["sender_name"] = m.group(1).strip()

    # Receiver Regex: Look for 'Sent to' or 'Paid to'
    m = re.search(
        r"(?:To|Receiver|Recipient|Beneficiary|Credit\s*Account\s*Title|Paid\s*to|Sent\s*to)[:\s]+([A-Za-z\s]+?)(?:\r?\n|\s+\d{10,15}|\s*$)",
        text, re.IGNORECASE
    )
    if m:
        result["receiver_name"] = m.group(1).strip()

    # Amount Regex
    m = re.search(r"(?:Rs\.?|PKR|Amount)[:\s]*([\d,]+(?:\.\d{1,2})?)", text, re.IGNORECASE)
    if m:
        result["amount"] = f"Rs. {m.group(1).strip()}"

    # Date Regex: Handle month names (e.g., 01 May 2026) or numeric formats
    date_patterns = [
        r"(\d{1,2}\s+[A-Za-z]{3,10}\s+\d{2,4})",
        r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        r"([A-Za-z]{3,10}\s+\d{1,2},?\s+\d{2,4})"
    ]
    for dp in date_patterns:
        m = re.search(dp, text, re.IGNORECASE)
        if m:
            result["date"] = m.group(1).strip()
            break

    # Time Regex
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

    # ── Email configuration check ────────────────────────────────────────────
    use_gmail_api = bool(CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN)
    use_smtp      = bool(GMAIL_USER and GMAIL_APP_PASSWORD)
    if use_gmail_api:
        logger.info("✅ Email: Gmail OAuth2 API configured")
    elif use_smtp:
        logger.info("✅ Email: Gmail SMTP configured")
    else:
        logger.warning(
            "⚠️ Email NOT configured. Set either:\n"
            "  • GMAIL_USER + GMAIL_APP_PASSWORD  (for SMTP)\n"
            "  • CLIENT_ID + CLIENT_SECRET + REFRESH_TOKEN  (for Gmail API)"
        )

    logger.info(f"Frontend API URL: {FRONTEND_API_URL}")
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

        # ── Always track the customer in DB ───────────────────────────────────
        try:
            requests.post(
                f"{FRONTEND_API_URL.rstrip('/')}/api/customers",
                json={"phone_number": sender_number},
                timeout=5, verify=certifi.where(),
            )
        except Exception:
            pass

        # ══════════════════════════════════════════════════════════════════════
        # TEXT MESSAGE
        # ══════════════════════════════════════════════════════════════════════
        if message_type == "text":
            user_text = message.get("text", {}).get("body", "")
            logger.info(f"💬 User {sender_number} says: {user_text!r}")

            txt_lower = user_text.strip().lower()
            state     = pending_choice.get(sender_number)

            logger.info(f"📌 State for {sender_number}: {state!r}")

            # ── Fetch / Initialize Customer Profile ───────────────────────────
            c_data = {}
            try:
                c_resp = requests.get(f"{FRONTEND_API_URL.rstrip('/')}/api/customers", params={"phone": sender_number}, timeout=5, verify=certifi.where())
                if c_resp.ok:
                    c_data = c_resp.json()
            except Exception:
                pass

            customer = c_data.get("customer")
            import re as regex
            has_order_id = bool(regex.search(r"ORD-\d+", user_text.upper()))

            # ── State: awaiting customer onboarding ───────────────────────────
            if state == "awaiting_onboarding":
                try:
                    import google.generativeai as genai
                    import os
                    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("API_KEY")
                    if api_key:
                        configure = getattr(genai, "configure", None)
                        if callable(configure):
                            configure(api_key=api_key)
                    GenerativeModel = getattr(genai, "GenerativeModel", None)
                    if not callable(GenerativeModel):
                        raise AttributeError("GenerativeModel is not available in google.generativeai")
                    m = GenerativeModel("gemini-1.5-flash-latest")
                    prompt = f"Extract Name, Email, and CNIC from this text. Return strictly valid JSON with keys 'name', 'email', 'cnic'. Text: {user_text}"
                    
                    extracted = {"name": None, "email": None, "cnic": None}
                    try:
                        generate_content = getattr(m, "generate_content", None)
                        if not callable(generate_content):
                            raise AttributeError("generate_content is not available on GenerativeModel")
                        resp = generate_content(prompt)
                        import json
                        resp_text = getattr(resp, "text", "")
                        extracted = json.loads(resp_text.replace('```json', '').replace('```', '').strip())
                    except Exception as ai_err:
                        logger.warning(f"AI Onboarding extraction failed (quota?): {ai_err}. Falling back to regex.")
                        # Fallback: Simple comma-separated or space-separated extraction
                        # Example: Ali, ali@gmail.com, 12345-1234567-1
                        parts = [p.strip() for p in user_text.replace(',', ' ').split() if p.strip()]
                        for p in parts:
                            if '@' in p and '.' in p: extracted["email"] = p
                            elif regex.match(r"\d{5}-\d{7}-\d", p): extracted["cnic"] = p
                            elif not extracted["name"] and len(p) > 2: extracted["name"] = p
                    
                    payload = {"phone_number": sender_number}
                    if extracted.get("name"): payload["name"] = extracted["name"]
                    if extracted.get("email"): payload["email"] = extracted["email"]
                    if extracted.get("cnic"): payload["cnic"] = extracted["cnic"]
                    
                    logger.info(f"📤 Sending onboarding payload: {payload}")
                    c_post_resp = requests.post(f"{FRONTEND_API_URL.rstrip('/')}/api/customers", json=payload, timeout=5, verify=certifi.where())
                    logger.info(f"📥 Onboarding POST response: {c_post_resp.status_code} - {c_post_resp.text}")
                except Exception as e:
                    logger.error(f"Onboarding logic error: {e}")
                
                pending_choice.pop(sender_number, None)
                user_text = "hello"  # Force the greeting menu to trigger below!
                txt_lower = "hello"
                customer_name = locals().get("extracted", {}).get("name") if isinstance(locals().get("extracted"), dict) else "Valued Customer"
                customer = {"name": customer_name} # Bypass the block below and provide context name
            
            # If no name is found and they are not midway through a critical flow or asking about an order
            elif (not customer or not customer.get("name")) and not has_order_id:
                if state not in ("awaiting_bank_paid", "awaiting_payment_method"):
                    pending_choice[sender_number] = "awaiting_onboarding"
                    send_whatsapp_message(
                        sender_number,
                        "Welcome to AutoServe! 👋\n\nTo give you the best experience, please reply with your:\n*Name, Email, and CNIC*\n\n_(Example: Ali, ali@gmail.com, 12345-1234567-1)_"
                    )
                    return {"status": "ok"}

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

            # ── State: awaiting payment method choice (1 = COD, 2 = Bank) ─────
            # This catches text replies AFTER the payment menu is sent.
            # Without this, typing "2" falls through to the AI and returns products.
            if state == "awaiting_payment_method":
                if txt_lower in ("1", "cash", "cod", "cash on delivery"):
                    send_whatsapp_message(
                        sender_number,
                        "✅ Thank you for choosing *Cash on Delivery*. Your order will be processed shortly. 🎉"
                    )
                    try:
                        requests.post(
                            f"{FRONTEND_API_URL.rstrip('/')}/api/save-payment-method",
                            json={"phone": sender_number, "payment_method": "Cash on Delivery"},
                            timeout=8, verify=certifi.where()
                        )
                    except Exception:
                        pass
                    pending_choice.pop(sender_number, None)
                    return {"status": "ok"}

                elif txt_lower in ("2", "bank", "banking", "bank app", "transfer", "easypaisa", "jazzcash", "hbl"):
                    acct = "0088765789758"
                    send_whatsapp_message(
                        sender_number,
                        f"✅ Thank you for choosing *Banking App*.\n\n"
                        f"Please transfer the payment to:\n\n"
                        f"*Account: {acct}*\n\n"
                        f"After payment, send a screenshot of the transaction for order confirmation. 📸"
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
                    return {"status": "ok"}

                else:
                    send_whatsapp_message(
                        sender_number,
                        "Please reply with:\n\n"
                        "*1* — Cash on Delivery\n"
                        "*2* — Pay through banking app"
                    )
                return {"status": "ok"}

            # ══════════════════════════════════════════════════════════════════
            # MAIN MENU SHORTCUTS
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
            if state == "awaiting_choice" and not is_greeting(user_text):
                if txt_lower == "2" or "human" in txt_lower:
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
                    return {"status": "ok"}
                elif txt_lower == "1" or "chatbot" in txt_lower or "ai" in txt_lower:
                    name = customer.get("name") if customer else "there"
                    send_whatsapp_message(sender_number, f"Hi {name}, I'm Zara, the AI Assistant. How can I help you?")
                    pending_choice.pop(sender_number, None)
                    return {"status": "ok"}
                else:
                    send_whatsapp_message(
                        sender_number,
                        "Please reply with *1* for Chatbot or *2* for Human. You can also type *Chatbot* or *Human*."
                    )
                    return {"status": "ok"}

            # ── Bare menu input without active state ─────────────────────────
            # If user sends "1", "2", "chatbot", "human" etc. without any active
            # state, they are probably replying late to a menu. Show the menu again.
            if not state and txt_lower in ("1", "2", "chatbot", "human", "ai", "ai assistant"):
                name = customer.get("name") if customer else None
                greeting_name = f" {name}" if name else ""
                pending_choice[sender_number] = "awaiting_choice"
                send_whatsapp_message(
                    sender_number,
                    f"Hi{greeting_name}! 👋 Would you like to talk to:\n\n"
                    "1️⃣ *Chatbot* (AI Assistant)\n"
                    "2️⃣ *Human Agent*\n\n"
                    "Reply with *1* or *2*, or type *Chatbot* / *Human*."
                )
                logger.info(f"👋 Stale menu input detected, re-sent greeting menu to {sender_number}")
                return {"status": "ok"}

            # ── Direct Order Status Lookup ────────────────────────────────────
            # If user sends an Order ID, fetch status directly from DB
            if has_order_id:
                import re as _re
                order_id_match = _re.search(r"(ORD-\d+)", user_text.upper())
                if order_id_match:
                    found_order_id = order_id_match.group(1)
                    try:
                        order_resp = requests.get(
                            f"{FRONTEND_API_URL.rstrip('/')}/api/orders",
                            params={"order_id": found_order_id},
                            timeout=5, verify=certifi.where()
                        )
                        if order_resp.ok:
                            order_data = order_resp.json()
                            if order_data.get("ok") and order_data.get("order"):
                                o = order_data["order"]
                                status = o.get("status", "Unknown")
                                product = o.get("product", "your item")
                                
                                # Build a friendly status message
                                if status.lower() == "processing":
                                    status_msg = "is currently being *prepared* for shipment 📦"
                                elif status.lower() == "dispatched":
                                    status_msg = "has been *dispatched* and is on its way to you 🚚"
                                elif status.lower() == "delivered":
                                    status_msg = "has been *delivered* ✅"
                                else:
                                    status_msg = f"is currently *{status}*"
                                
                                customer_name = customer.get("name", "") if customer else ""
                                greeting = f"Hi {customer_name}! " if customer_name else ""
                                
                                reply = (
                                    f"{greeting}Here's the update on your order:\n\n"
                                    f"📋 *Order ID:* {found_order_id}\n"
                                    f"🛍️ *Product:* {product}\n"
                                    f"📌 *Status:* Your order {status_msg}\n\n"
                                    f"Is there anything else I can help you with?"
                                )
                                send_whatsapp_message(sender_number, reply)
                                logger.info(f"📦 Order status sent for {found_order_id}: {status}")
                                return {"status": "ok"}
                            else:
                                send_whatsapp_message(
                                    sender_number,
                                    f"Sorry, I couldn't find an order with ID *{found_order_id}*. Please double-check and try again."
                                )
                                return {"status": "ok"}
                        else:
                            send_whatsapp_message(
                                sender_number,
                                f"Sorry, I couldn't find an order with ID *{found_order_id}*. Please double-check and try again."
                            )
                            return {"status": "ok"}
                    except Exception as e:
                        logger.error(f"Order lookup error: {e}")
                        send_whatsapp_message(
                            sender_number,
                            "Sorry, I'm having trouble looking up your order right now. Please try again in a moment."
                        )
                        return {"status": "ok"}

            # ── Greeting ──────────────────────────────────────────────────────
            # If it's a greeting but NOT an order tracking request, show the menu
            if is_greeting(user_text) and not has_order_id:
                name = customer.get("name") if customer else None
                greeting_name = f" {name}" if name else ""
                
                pending_choice[sender_number] = "awaiting_choice"
                send_whatsapp_message(
                    sender_number,
                    f"Hi{greeting_name}! 👋 Would you like to talk to:\n\n"
                    "1️⃣ *Chatbot* (AI Assistant)\n"
                    "2️⃣ *Human Agent*\n\n"
                    "Reply with *1* or *2*, or type *Chatbot* / *Human*."
                )
                logger.info(f"👋 Sent personalized greeting menu to {sender_number} (Name: {name})")
                return {"status": "ok"}

            # ── Default: AI chat ──────────────────────────────────────────────
            context_text = ""
            is_returning = c_data.get("is_returning") if c_data else False
            orders = c_data.get("orders", []) if c_data else []
            name = customer.get("name") if customer else None
            
            if name:
                context_text += f"Customer Name: {name}. "
                
            if is_returning:
                context_text += f"Status: Returning Customer. "
                if orders:
                    last_order = orders[0]
                    context_text += f"Last Order: {last_order.get('product')} (ID: {last_order.get('order_id')}, Status: {last_order.get('status')}). "
            else:
                context_text += f"Status: New Customer. "

            bot_reply = get_chat_response(sender_number, user_text, context_text=context_text)
            logger.info(f"🤖 Zara replies: {bot_reply!r}")
            send_whatsapp_message(sender_number, bot_reply)

            # Check if an order was just placed and trigger payment flow
            if is_successful_order_placement(bot_reply):
                order_id = extract_order_id(bot_reply)
                logger.info(f"🛒 Order detected: {order_id}")
                _send_order_email(order_id, sender_number, user_text, bot_reply)
                send_payment_buttons(sender_number)
                # ✅ Set state so text reply "1" or "2" is caught before AI
                pending_choice[sender_number] = "awaiting_payment_method"


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
        # IMAGE MESSAGE — ALWAYS run OCR, save transaction, notify email
        # Works for both payment screenshots and standalone transaction images.
        # ══════════════════════════════════════════════════════════════════════
        elif message_type == "image":
            media_id = message.get("image", {}).get("id")
            if not media_id:
                send_whatsapp_message(sender_number, "❌ Could not read image. Please try again.")
            else:
                is_payment_confirmation = pending_choice.get(sender_number) == "awaiting_bank_paid"


                if is_payment_confirmation:
                    try:
                        requests.post(
                            f"{FRONTEND_API_URL.rstrip('/')}/api/save-payment-method",
                            json={"phone": sender_number, "payment_method": "Bank App", "status": "screenshot_received"},
                            timeout=8, verify=certifi.where()
                        )
                    except Exception:
                        pass
                    pending_choice.pop(sender_number, None)

                # ── Always run OCR and save the transaction data ──────────────
                try:

                    img      = download_whatsapp_image(media_id)
                    raw_text = preprocess_and_ocr(img)
                    logger.info(f"📝 OCR text: {raw_text[:300]}")

                    if not raw_text.strip() or raw_text.startswith("[Image received - OCR"):
                        send_whatsapp_message(
                            sender_number,
                            "❌ Could not read text from the image. Please send a clearer screenshot."
                        )
                    else:
                        fields = extract_transaction_fields(raw_text)
                        logger.info(f"✅ Fields extracted: {fields}")

                        # ── Save to DB ────────────────────────────────────────
                        row_id = None
                        try:
                            row_id = save_transaction_record(fields, raw_text, sender_number)
                            logger.info(f"✅ Transaction saved — DB row id={row_id}")
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to save transaction: {e}")

                        # ── Customer activity is now tracked automatically in DB ──
                        tx_ref = fields.get("transaction_id") or (f"TX-{row_id}" if row_id is not None else None)

                        # ── Send email notification ───────────────────────────
                        try:
                            email_ok = send_transaction_summary_email(fields, raw_text, sender_number, row_id=row_id)
                            if email_ok:
                                logger.info(f"✅ Transaction email sent for {fields.get('transaction_id') or row_id}")
                            else:
                                logger.warning(f"⚠️ Transaction email not sent for {fields.get('transaction_id') or row_id}")
                        except Exception as e:
                            logger.warning(f"⚠️ Email notification failed: {e}")

                        # ── Reply to user with extracted transaction card only ──
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
    access_token = get_whatsapp_access_token()
    if not access_token:
        return {"error": "Missing WhatsApp access token"}
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