import asyncio
import sys
import re
from chrome_lens_py import LensAPI

sys.stdout.reconfigure(encoding='utf-8')

def parse_question_from_ocr(ocr_text, word_data=None):
    """
    Cleans up mobile/web screenshot artifacts (status bar, timers, headers, footers)
    and formats quiz questions cleanly like Image 2:
    Câu [X]: [Nội dung câu hỏi]
    [Ghi chú/Hướng dẫn]
    A. [Nội dung A]
    B. [Nội dung B]
    C. [Nội dung C]
    D. [Nội dung D]
    """
    lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
    
    # Filter out common UI headers / status bar junk:
    # e.g. "20:05", "59", "Kiểm tra tuần", "12:42", "<", "Câu hỏi 14/15", "14/15"
    cleaned_lines = []
    
    # Regex patterns for junk:
    time_pat = re.compile(r'^\d{1,2}:\d{2}(:\d{2})?$')
    battery_pat = re.compile(r'^\d{1,3}%?$')
    nav_pat = re.compile(r'^(<|>|<<|>>|Quay lại|Tiếp tục|Nộp bài|Câu hỏi \d+[\s/]+\d+|\d+[\s/]+\d+)$', re.IGNORECASE)
    header_keywords = ['kiểm tra tuần', 'bài kiểm tra', 'thời gian còn lại', 'trả lời:']
    
    for line in lines:
        if time_pat.match(line):
            continue
        if battery_pat.match(line) and len(line) <= 3:
            continue
        if nav_pat.match(line):
            continue
        if line.lower() in header_keywords:
            continue
        if line == '<' or line == '>' or line == '«' or line == '»':
            continue
        cleaned_lines.append(line)
        
    return cleaned_lines

async def main():
    api = LensAPI()
    img_path = r'C:/Users/Admin/.gemini/antigravity/brain/6c1697e7-a772-43bc-a2ea-e903297d2688/.user_uploaded/media_1791816293985_5ed3682e.png'
    res = await api.process_image(img_path)
    ocr_text = res.get('ocr_text', '')
    cleaned = parse_question_from_ocr(ocr_text)
    print("=== CLEANED LINES ===")
    for l in cleaned:
        print(l)
    await api.aclose()

if __name__ == '__main__':
    asyncio.run(main())
