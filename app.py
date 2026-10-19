import os
import sys
import io
import re
import time
import json
import base64
import asyncio
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from PIL import Image
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from chrome_lens_py import LensAPI

sys.stdout.reconfigure(encoding='utf-8')

# Global persistent LensAPI instance for maximum connection reuse & speed
lens_api: Optional[LensAPI] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global lens_api
    # Initialize LensAPI with connection pooling
    lens_api = LensAPI()
    print("⚡ Google Lens OCR Engine initialized and ready.")
    yield
    if lens_api:
        await lens_api.aclose()
        print("Google Lens OCR Engine closed.")

app = FastAPI(title="Lens Quiz OCR", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def smart_format_quiz(ocr_text: str) -> Dict[str, Any]:
    """
    Cleans phone/web screenshot artifacts (status bar, timer, battery, navigation buttons)
    and formats quiz questions cleanly like Image 2.
    Robustly handles multi-line options, selected radio buttons, and OCR ambiguities.
    """
    if not ocr_text:
        return {
            "smart_text": "",
            "raw_text": "",
            "question_title": "",
            "instruction": "",
            "options": [],
            "search_query": ""
        }

    raw_lines = [l.strip() for l in ocr_text.splitlines() if l.strip()]

    # 1. BẮT ĐẦU CHÍNH XÁC TỪ DÒNG "CÂU" (Bỏ sạch toàn bộ 'Kiểm tra tuần', pin, đồng hồ phía trên)
    start_idx = 0
    for idx, l in enumerate(raw_lines):
        if re.search(r'^\s*(Câu\s*hỏi\s*\d+|Câu\s*\d+|Câu\s*:|Bài\s*\d+)', l, re.IGNORECASE):
            start_idx = idx
            break

    lines_from_cau = raw_lines[start_idx:]

    # 2. Lọc bỏ các phần tử rác dưới dòng Câu
    time_pat = re.compile(r'^\d{1,2}:\d{2}(:\d{2})?$')
    battery_pat = re.compile(r'^\d{1,3}%?$')
    page_pat = re.compile(r'^(\d+[\s/]+\d+|<\s*\d+[\s/]+\d+\s*>)$')
    nav_pat = re.compile(r'^(<|>|<<|>>|«|»|Quay lại|Tiếp tục|Nộp bài|Câu hỏi \d+[\s/]+\d+|\d+[\s/]+\d+)$', re.IGNORECASE)

    ui_junk_keywords = [
        'kiểm tra tuần', 'thời gian còn lại', 'thời gian làm bài', 'bài kiểm tra', 
        'trả lời:', 'trả lời', 'tra lời', 'trà lời', 'trà 10%', 'trả 10%', 'tra 10%',
        'đáp án:', 'đáp án', 'câu tiếp theo', 'quay lại', 'tiếp theo', 'câu hỏi'
    ]

    filtered = []
    for l in lines_from_cau:
        lower = l.lower()
        if lower in ui_junk_keywords:
            continue
        if any(lower.startswith(k) for k in ['kiểm tra tuần', 'thời gian còn lại', 'thời gian làm bài', 'bài kiểm tra']):
            continue
        if any(lower.startswith(k) for k in ['trả lời', 'tra lời', 'trà lời', 'trà 10%', 'trả 10%']):
            continue
        if time_pat.match(l) or (battery_pat.match(l) and len(l) <= 3) or page_pat.match(l) or nav_pat.match(l):
            continue
        if lower in ['<', '>', '«', '»']:
            continue
        filtered.append(l)


    def match_option_start(line, last_key=None):
        raw_l = line.strip()

        # Check OCR artifact for D: 'O Visual Studio Code' or '0 Visual Studio Code' when previous option was C
        if last_key == 'C':
            m_o = re.match(r'^[oO0][\.\:\)\-]?\s+([A-ZÀ-Ỹ].*)$', raw_l)
            if m_o:
                return 'D', m_o.group(1).strip()

        # Check OCR artifact for B: '8. text' when previous was A
        if last_key == 'A':
            m_8 = re.match(r'^8[\.\:\)\-]?\s*(.*)$', raw_l)
            if m_8:
                return 'B', m_8.group(1).strip()

        cleaned = re.sub(r'^[\[\(][\s_xX✓✔oO0]?[\)\]]\s*', '', raw_l)
        cleaned = re.sub(r'^[•\-\*▪▫]\s*', '', cleaned)
        cleaned = re.sub(r'^[oO0]\s+', '', cleaned)

        # Exact single letter 'A', 'B', 'C', 'D'
        m_single = re.match(r'^([A-F])[\.\:\)]?$', cleaned, re.IGNORECASE)
        if m_single:
            return m_single.group(1).upper(), ""

        # Letter with punctuation: 'A. text', 'A) text', 'A: text', 'A - text'
        m_punct = re.match(r'^([A-F])[\.\:\)\-]\s*(.*)$', cleaned, re.IGNORECASE)
        if m_punct:
            return m_punct.group(1).upper(), m_punct.group(2).strip()

        # Letter with space: 'A Text' (MUST NOT be word like Dùng, Bạn, etc.)
        m_space = re.match(r'^([A-F])\s+([A-ZÀ-Ỹ0-9].*)$', cleaned)
        if m_space:
            return m_space.group(1).upper(), m_space.group(2).strip()

        return None, None

    first_opt_idx = -1
    for idx, l in enumerate(filtered):
        let, _ = match_option_start(l)
        if let == 'A':
            first_opt_idx = idx
            break

    if first_opt_idx == -1:
        for idx, l in enumerate(filtered):
            let, _ = match_option_start(l)
            if let in ['A', 'B', 'C', 'D']:
                first_opt_idx = idx
                break

    if first_opt_idx == -1:
        question_lines = filtered
        opt_lines = []
    else:
        question_lines = filtered[:first_opt_idx]
        opt_lines = filtered[first_opt_idx:]

    cau_prefix = ""
    instructions = []
    q_body_parts = []

    for l in question_lines:
        lower = l.lower()
        if (l.startswith('(') and l.endswith(')')) or ('chọn' in lower and ('đáp án' in lower or 'nhất' in lower)):
            instructions.append(l)
            continue

        m_cau = re.match(r'^(Câu\s*hỏi\s*\d+|Câu\s*\d+|Bài\s*\d+)\s*[:.\-]?\s*(.*)$', l, re.IGNORECASE)
        if m_cau:
            cau_prefix = m_cau.group(1).strip() + ':'
            rest = m_cau.group(2).strip()
            if rest:
                q_body_parts.append(rest)
        else:
            q_body_parts.append(l)

    full_q = (f"{cau_prefix} " if cau_prefix else "") + " ".join(q_body_parts)
    full_q = full_q.strip()

    options = []
    current_key = None
    current_text_parts = []
    expected_letters = ['A', 'B', 'C', 'D', 'E', 'F']

    for l in opt_lines:
        let, content = match_option_start(l, last_key=current_key)

        is_new_option = False
        if let:
            if not current_key or expected_letters.index(let) >= expected_letters.index(current_key):
                is_new_option = True

        if is_new_option:
            if current_key:
                options.append({"key": current_key, "text": " ".join(current_text_parts).strip()})
            current_key = let
            current_text_parts = [content] if content else []
        else:
            if current_key:
                current_text_parts.append(l)

    if current_key:
        options.append({"key": current_key, "text": " ".join(current_text_parts).strip()})

    q_body = " ".join(q_body_parts).strip()
    smart_lines = []
    if full_q:
        smart_lines.append(full_q)
    for inst in instructions:
        smart_lines.append(inst)
    for opt in options:
        smart_lines.append(f"{opt['key']}. {opt['text']}")
    smart_text = "\n".join(smart_lines)

    smart_lines_no_prefix = []
    if q_body:
        smart_lines_no_prefix.append(q_body)
    elif full_q:
        clean_first = re.sub(r'^\s*(Câu\s*hỏi\s*\d+|Câu\s*\d+|Bài\s*\d+|\d+)\s*[:.\-]?\s*', '', full_q, flags=re.IGNORECASE).strip()
        if clean_first:
            smart_lines_no_prefix.append(clean_first)
    for inst in instructions:
        smart_lines_no_prefix.append(inst)
    for opt in options:
        smart_lines_no_prefix.append(f"{opt['key']}. {opt['text']}")
    smart_text_no_prefix = "\n".join(smart_lines_no_prefix)

    search_q = full_q
    if search_q:
        search_q = re.sub(r'^\s*(Câu\s*hỏi\s*\d+|Câu\s*\d+|Bài\s*\d+|\d+)\s*[:.\-]?\s*', '', search_q, flags=re.IGNORECASE).strip()

    return {
        "smart_text": smart_text,
        "smart_text_no_prefix": smart_text_no_prefix,
        "cau_prefix": cau_prefix,
        "question_body": q_body,
        "raw_text": ocr_text,
        "question_title": full_q,
        "instruction": "\n".join(instructions),
        "options": options,
        "search_query": search_q
    }



class CropBox(BaseModel):
    x: float
    y: float
    width: float
    height: float

class OCRRequest(BaseModel):
    image_base64: Optional[str] = None
    crop: Optional[CropBox] = None

@app.post("/api/ocr")
async def process_ocr(
    file: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None),
    crop_x: Optional[float] = Form(None),
    crop_y: Optional[float] = Form(None),
    crop_w: Optional[float] = Form(None),
    crop_h: Optional[float] = Form(None),
):
    global lens_api
    if not lens_api:
        lens_api = LensAPI()

    t_start = time.perf_counter()
    image_bytes = None

    if file:
        image_bytes = await file.read()
    elif image_base64:
        if "," in image_base64:
            image_base64 = image_base64.split(",", 1)[1]
        image_bytes = base64.b64decode(image_base64)
    else:
        raise HTTPException(status_code=400, detail="Không tìm thấy hình ảnh nào để xử lý.")

    # Handle cropping if requested
    if crop_x is not None and crop_y is not None and crop_w and crop_h:
        try:
            with Image.open(io.BytesIO(image_bytes)) as pil_img:
                img_w, img_h = pil_img.size
                left = max(0, int(crop_x * img_w))
                top = max(0, int(crop_y * img_h))
                right = min(img_w, int((crop_x + crop_w) * img_w))
                bottom = min(img_h, int((crop_y + crop_h) * img_h))
                
                if right > left and bottom > top:
                    cropped = pil_img.crop((left, top, right, bottom))
                    buf = io.BytesIO()
                    cropped.save(buf, format="PNG")
                    image_bytes = buf.getvalue()
        except Exception as e:
            print(f"Lỗi crop: {e}")

    try:
        # Call Google Lens API directly
        lens_res = await lens_api.process_image(image_bytes)
        ocr_text = lens_res.get("ocr_text", "")
        word_data = lens_res.get("word_data", [])
    except Exception as e:
        print(f"Lỗi LensAPI: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi nhận diện Google Lens: {str(e)}")

    t_end = time.perf_counter()
    duration_ms = round((t_end - t_start) * 1000)

    # Smart parse
    parsed = smart_format_quiz(ocr_text)

    return {
        "success": True,
        "duration_ms": duration_ms,
        "smart_text": parsed["smart_text"],
        "smart_text_no_prefix": parsed["smart_text_no_prefix"],
        "cau_prefix": parsed.get("cau_prefix", ""),
        "question_body": parsed.get("question_body", ""),
        "raw_text": parsed["raw_text"],
        "question_title": parsed["question_title"],
        "instruction": parsed["instruction"],
        "options": parsed["options"],
        "search_query": parsed["search_query"],
        "word_count": len(word_data),
        "words": [
            {
                "word": w.get("word", ""),
                "geom": w.get("geometry", {})
            }
            for w in word_data
        ]
    }

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    with open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "engine": "google-lens"}

@app.get("/favicon.ico")
async def favicon():
    svg_icon = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#1a73e8"><path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"/><path d="M4 4h3l2-2h6l2 2h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2m8 3a5 5 0 1 0 0 10 5 5 0 0 0 0-10Z"/></svg>'''
    return Response(content=svg_icon, media_type="image/svg+xml")

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "history.json")

def load_history_file() -> List[Dict[str, Any]]:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Lỗi đọc history.json: {e}")
    return []

def save_history_file(data: List[Dict[str, Any]]):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data[:100], f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Lỗi lưu history.json: {e}")

@app.get("/api/history")
async def get_history():
    return load_history_file()

@app.post("/api/history")
async def save_history(request: Request):
    try:
        body = await request.json()
        if isinstance(body, list):
            save_history_file(body)
            return {"status": "ok", "count": len(body)}
        return {"status": "ignored"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/history")
async def clear_history():
    save_history_file([])
    return {"status": "ok"}


def open_browser(port=8000):
    url = f"http://127.0.0.1:{port}"
    try:
        os.startfile(url)
        return
    except Exception:
        pass
    try:
        import subprocess
        subprocess.Popen(f'start "" "{url}"', shell=True)
        return
    except Exception:
        pass
    import webbrowser
    webbrowser.open(url)

def wait_and_open_browser(port=8000):
    """Đợi server phản hồi 200 OK trước khi mở trình duyệt, tránh mở sớm bị lỗi connection refused."""
    import urllib.request
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):  # Chờ tối đa 12 giây
        time.sleep(0.2)
        try:
            req = urllib.request.Request(f"{url}/api/health")
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                if resp.status == 200:
                    break
        except Exception:
            pass
    open_browser(port)

def free_port(port=8000):
    """Frees the port if occupied by any stale process."""
    try:
        import subprocess
        output = subprocess.check_output("netstat -ano", shell=True).decode(errors="ignore")
        for line in output.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = parts[-1]
                if pid and pid != "0" and pid != str(os.getpid()):
                    print(f"Giải phóng tiến trình cũ PID {pid} trên cổng {port}...")
                    subprocess.call(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(0.5)
    except Exception as e:
        print(f"Kiểm tra cổng: {e}")

def get_free_port(start_port=8000, max_tries=10) -> int:
    free_port(start_port)
    import socket
    for p in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', p)) != 0:
                return p
    return start_port

if __name__ == "__main__":
    import threading
    import uvicorn

    port = 8000
    actual_port = get_free_port(port)

    # Tự động mở giao diện ngay khi server đã khởi động xong 100%
    threading.Thread(target=wait_and_open_browser, args=(actual_port,), daemon=True).start()

    print(f"\n=======================================================")
    print(f"  GOOGLE LENS QUIZ OCR - PHẢN HỒI SIÊU TỐC (~0.4s)")
    print(f"  Địa chỉ: http://127.0.0.1:{actual_port}")
    print(f"  Nhấn Ctrl + C để dừng máy chủ.")
    print(f"=======================================================\n")

    uvicorn.run(app, host="127.0.0.1", port=actual_port)


