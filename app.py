from fastapi import FastAPI, Request, Query, Response
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Credentials from your .env


ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# 1. VERIFICATION (For Meta to verify your link)
@app.get("/webhook")
async def verify(
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge")
):
    if token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Error", status_code=403)

# 2. RECEIVE & REPLY (The actual bot logic)
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    
    try:
        # Navigate the JSON structure to find the message
        if "messages" in data["entry"][0]["changes"][0]["value"]:
            message = data["entry"][0]["changes"][0]["value"]["messages"][0]
            sender_number = message["from"]
            user_text = message["text"]["body"]

            print(f"Received from {sender_number}: {user_text}")

            # Send the reply back
            send_whatsapp_message(sender_number, f"FastAPI Bot says: I received '{user_text}'")
            
    except Exception as e:
        print(f"Error: {e}")

    return {"status": "success"}

def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}


    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    res = requests.post(url, headers=headers, json=payload)
    print("Meta Response:", res.json())