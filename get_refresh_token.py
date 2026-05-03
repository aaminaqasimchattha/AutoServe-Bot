import os
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ Error: CLIENT_ID and CLIENT_SECRET must be set in your .env file!")
    exit(1)

# The redirect URI you requested
redirect_uri = "https://jone-fumiest-unabsorbingly.ngrok-free.dev/gmail/callback"

auth_url = (
    "https://accounts.google.com/o/oauth2/v2/auth"
    f"?scope=https://www.googleapis.com/auth/gmail.send"
    "&access_type=offline"
    "&prompt=consent"
    "&response_type=code"
    f"&redirect_uri={redirect_uri}"
    f"&client_id={CLIENT_ID}"
)

print("\n" + "="*80)
print("GOOGLE OAUTH2 SETUP FOR GMAIL REST API")
print("="*80)
print(f"Authorized Redirect URI to set in Google Console: {redirect_uri}")
print("="*80)
print("\nSTEP 1: Please visit this authorization URL in your browser:\n")
print(auth_url)
print("\n" + "="*80)

print("\nSTEP 2: Sign in and click 'Allow'. Your browser will redirect you to a page.")
print("The URL in the address bar will look like this:")
print("https://jone-fumiest-unabsorbingly.ngrok-free.dev/gmail/callback?code=4/0AbUR2VO...")
print("\nCopy the 'code' parameter from the address bar.")

code = input("\nSTEP 3: Paste that code here: ").strip()

# Strip any URL and just keep the code parameter if they accidentally paste the whole URL
if "code=" in code:
    from urllib.parse import urlparse, parse_qs
    parsed = parse_qs(urlparse(code).query)
    if "code" in parsed:
        code = parsed["code"][0]

if code:
    print("\nAttempting to exchange code for Refresh Token...")
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
        data = res.json()
        if "refresh_token" in data:
            refresh_token = data["refresh_token"]
            print("\n✅ Success!")
            print(f"Refresh Token: {refresh_token}")
            
            # Save to .env file directly
            env_path = os.path.join(os.path.dirname(__file__), ".env")
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
                # Filter out old REFRESH_TOKEN
                lines = [line for line in lines if not line.strip().startswith("REFRESH_TOKEN=")]
                lines.append(f"REFRESH_TOKEN={refresh_token}")
                
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                print("💾 Saved the REFRESH_TOKEN to your .env file!")
            else:
                print("⚠️ .env file not found. Please add this manually to your .env file:")
                print(f"REFRESH_TOKEN={refresh_token}")
        else:
            print("\n❌ Failed to obtain refresh token. Google's response:")
            print(data)
    except Exception as e:
        print(f"\n❌ Error connecting to Google token endpoint: {e}")
