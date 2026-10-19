import asyncio
import sys
import io
from PIL import Image
from chrome_lens_py import LensAPI

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    img = Image.open(r'C:/Users/Admin/.gemini/antigravity/brain/6c1697e7-a772-43bc-a2ea-e903297d2688/.user_uploaded/media_1791819115887_62b246ce.png')
    w, h = img.size
    # Crop phone on the left: x: 0.10 to 0.36, y: 0.08 to 0.92
    cropped = img.crop((int(w * 0.10), int(h * 0.08), int(w * 0.36), int(h * 0.92)))
    
    buf = io.BytesIO()
    cropped.save(buf, format='PNG')
    
    api = LensAPI()
    res = await api.process_image(buf.getvalue())
    print("=== RAW OCR TEXT ===")
    print(res.get('ocr_text', ''))
    print("=== ALL WORDS WITH COORDS ===")
    words = res.get('word_data', [])
    for w in sorted(words, key=lambda x: (x.get('geometry', {}).get('center_y', 0), x.get('geometry', {}).get('center_x', 0))):
        g = w.get('geometry', {})
        print(f"y={g.get('center_y', 0):.3f}, x={g.get('center_x', 0):.3f} | {w.get('word')}")
    await api.aclose()

if __name__ == '__main__':
    asyncio.run(main())
