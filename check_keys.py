
import os
from dotenv import load_dotenv

load_dotenv()

required = ["DEEPGRAM_API_KEY", "CARTESIA_API_KEY", "OPENAI_API_KEY"]
found = []
missing = []

for key in required:
    val = os.environ.get(key)
    if val:
        found.append(f"{key}=...{val[-4:]}")
    else:
        missing.append(key)

print(f"Found keys: {found}")
print(f"Missing keys: {missing}")

if "DEEPGRAM_API_KEY" in missing:
    print("CRITICAL: Deepgram (STT) key missing. LiveKit Agent will be deaf.")
if "CARTESIA_API_KEY" in missing:
    print("CRITICAL: Cartesia (TTS) key missing. LiveKit Agent will be mute.")
