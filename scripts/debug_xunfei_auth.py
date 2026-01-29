
import asyncio
import base64
import datetime
import hashlib
import hmac
import json
import ssl
import sys
import websockets
from urllib.parse import urlencode, urlparse

APP_ID = "57a8697d"
API_KEY = "7de586494bb83ef31d1309701c77b120"
API_SECRET_RAW = "Yjk5YjEwNTdlMmFjOWRhOWZjNWFkOTg0"

def get_auth_url(url, api_key, api_secret):
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path
    
    # RFC1123 date
    date = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    
    # Handle secret being bytes or string
    secret_bytes = api_secret.encode('utf-8') if isinstance(api_secret, str) else api_secret
    
    signature_sha = hmac.new(
        secret_bytes,
        signature_origin.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    
    signature = base64.b64encode(signature_sha).decode('utf-8')
    
    authorization_origin = (
        f'api_key="{api_key}", '
        f'algorithm="hmac-sha256", '
        f'headers="host date request-line", '
        f'signature="{signature}"'
    )
    
    authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
    
    v = {
        "host": host,
        "date": date,
        "authorization": authorization
    }
    
    return url + "?" + urlencode(v)

async def test_connection(url, secret, name):
    print(f"Testing {name}...")
    print(f"  URL: {url}")
    # print(f"  Secret: {secret}")
    
    auth_url = get_auth_url(url, API_KEY, secret)
    
    try:
        async with websockets.connect(auth_url, ssl=ssl.create_default_context()) as ws:
            print(f"  ✅ SUCCESS! Connected to {name}")
            return True
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"  ❌ FAILED: {e.status_code} {e}")
        return False
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False

async def main():
    endpoints = [
        ("CN_STT", "wss://iat-api.xfyun.cn/v2/iat"),
        ("CN_TTS", "wss://tts-api.xfyun.cn/v2/tts"),
        ("SG_STT", "wss://iat-api-sg.xf-yun.com/v2/iat"),
        ("SG_TTS", "wss://tts-api-sg.xf-yun.com/v2/tts"),
    ]
    
    # Prepare secrets
    secret_raw = API_SECRET_RAW
    
    try:
        secret_decoded_str = base64.b64decode(API_SECRET_RAW).decode('utf-8')
    except:
        secret_decoded_str = "DECODE_FAILED"
        
    try:
        secret_decoded_bytes = base64.b64decode(API_SECRET_RAW)
    except:
        secret_decoded_bytes = b""

    secrets = [
        ("Raw String", secret_raw),
        # ("Decoded String", secret_decoded_str),
        # ("Decoded Bytes", secret_decoded_bytes),
    ]

    results = []
    
    for ep_name, ep_url in endpoints:
        for sec_name, sec_val in secrets:
            if sec_val == "DECODE_FAILED": continue
            
            test_name = f"{ep_name} + {sec_name}"
            success = await test_connection(ep_url, sec_val, test_name)
            results.append((test_name, success))
            print("-" * 40)

    print("\nSummary:")
    for name, success in results:
        print(f"{'✅' if success else '❌'} {name}")

if __name__ == "__main__":
    asyncio.run(main())
