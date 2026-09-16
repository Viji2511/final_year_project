import os, base64, json, sys
from dotenv import load_dotenv
from groq import Groq

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 1x1 white PNG (binary-safe)
WHITE_1x1_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YGD4z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
)

# Skip known non-chat / audio models
SKIP_MODELS = {"whisper-large-v3", "whisper-large-v3-turbo", "canopylabs/orpheus-v1-english", "canopylabs/orpheus-arabic-saudi"}

candidates = [m.id for m in client.models.list().data]

results = {}
for model_id in candidates:
    if model_id in SKIP_MODELS:
        print(f"SKIP (non-chat): {model_id}")
        results[model_id] = {"vision_capable": False, "error": "non-chat model"}
        continue
    try:
        resp = client.chat.completions.create(
            model=model_id,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image in one word."},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{WHITE_1x1_PNG_B64}"
                    }}
                ]
            }],
            max_tokens=20,
        )
        results[model_id] = {
            "vision_capable": True,
            "response": resp.choices[0].message.content.strip()
        }
        print(f"VISION OK: {model_id} -> {results[model_id]['response']}")
    except Exception as e:
        err_str = str(e)
        results[model_id] = {"vision_capable": False, "error": err_str[:200]}
        print(f"VISION FAIL: {model_id} -> {err_str[:120]}")

print("\n=== VISION-CAPABLE MODELS ===")
for m, r in results.items():
    if r.get("vision_capable"):
        print(f"  {m}")

