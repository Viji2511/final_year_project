"""
Probe qwen/qwen3.8-27b with an actual figure extracted from the NIPS PDF.
Images are resized to <=512px to keep payload within API limits.
"""
import sys, os, base64, fitz, io
from dotenv import load_dotenv
from groq import Groq
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "qwen/qwen3.8-27b"
PDF = r"mrep_bench\papers\NIPS-2017-self-normalizing-neural-networks-Paper.pdf"
MAX_DIM = 512  # resize to max this dimension

def resize_image(img_bytes: bytes, max_dim: int = MAX_DIM) -> tuple[str, bytes]:
    """Resize image so max(w,h) <= max_dim, return (ext, resized_bytes)."""
    img = Image.open(io.BytesIO(img_bytes))
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "png", buf.getvalue()

# Extract first usable figure from PDF
doc = fitz.open(PDF)
found_images = []
for page_num, page in enumerate(doc):
    for img_idx, img in enumerate(page.get_images(full=True)):
        xref = img[0]
        base_img = doc.extract_image(xref)
        if base_img["width"] < 100 or base_img["height"] < 100:
            continue
        found_images.append((page_num, img_idx, base_img))
        if len(found_images) >= 3:
            break
    if len(found_images) >= 3:
        break
doc.close()

if not found_images:
    print("ERROR: No suitable figure found in PDF.")
    sys.exit(1)

for page_num, img_idx, base_img in found_images:
    fig_id = f"fig_{page_num+1}_{img_idx+1}"
    orig_w, orig_h = base_img["width"], base_img["height"]
    
    resized_ext, resized_bytes = resize_image(base_img["image"])
    test_image_b64 = base64.b64encode(resized_bytes).decode("utf-8")
    
    print(f"\n--- Testing {fig_id} (orig {orig_w}x{orig_h}px, resized b64={len(test_image_b64)} chars) ---")
    print(f"Sending to {MODEL} ...")
    
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "What kind of chart or figure is shown in this image? Describe briefly."},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/{resized_ext};base64,{test_image_b64}"
                    }}
                ]
            }],
            max_tokens=200,
            temperature=0,
        )
        print(f"SUCCESS - finish_reason: {resp.choices[0].finish_reason}")
        print(f"Response: {resp.choices[0].message.content}")
        print(f"\n=> {MODEL} ACCEPTS image input with resized real figures.")
        break
    except Exception as e:
        print(f"FAIL: {e}")

