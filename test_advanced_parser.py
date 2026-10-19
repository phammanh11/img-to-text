import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

raw = '''19:29
Kiểm tra tuần
13:40
Câu 14:
Sau khi khởi động Anaconda Navigator, bạn muốn mở một
trình biên tập mã đơn giản để viết và chạy Python. Bạn nên
chọn công cụ nào?
Tra lời
A Anaconda Prompt
8. Git Bash
C. Jupyter Notebook
O Visual Studio Code
<
Câu hỏi
14/15'''

def smart_format_advanced(ocr_text):
    lines = [l.strip() for l in ocr_text.splitlines() if l.strip()]
    
    # Filter header / footer junk
    time_pat = re.compile(r'^\d{1,2}:\d{2}(:\d{2})?$')
    battery_pat = re.compile(r'^\d{1,3}%?$')
    junk_exact = {'<', '>', '«', '»', 'câu hỏi', 'trả lời:', 'trả lời', 'tra lời', 'đáp án:', 'đáp án', 'bài kiểm tra'}
    
    filtered = []
    for l in lines:
        lower = l.lower()
        if lower in junk_exact:
            continue
        if time_pat.match(l) or (battery_pat.match(l) and len(l) <= 3):
            continue
        if lower.startswith(('kiểm tra tuần', 'thời gian còn lại', 'thời gian làm bài', 'bài thi', 'môn:')):
            continue
        if lower.startswith('câu hỏi ') and re.search(r'\d+\s*/\s*\d+', l):
            continue
        if re.match(r'^\d+\s*/\s*\d+$', l):
            continue
        filtered.append(l)

    # Separate Question part and Options part
    q_lines = []
    opt_raw_lines = []
    in_options = False
    
    for l in filtered:
        # Check if line looks like start of options
        if not in_options:
            if re.match(r'^[A-D][\.\:\)]\s*', l, re.IGNORECASE) or re.match(r'^[A-D]\s+[A-ZÀ-Ỹ]', l) or l.startswith(('O A.', 'O B.', 'O C.', 'O D.', 'O A', 'O B', 'O C', 'O D')):
                in_options = True
                opt_raw_lines.append(l)
            else:
                q_lines.append(l)
        else:
            opt_raw_lines.append(l)
            
    # Process question lines:
    cau_prefix = ''
    body_parts = []
    for ql in q_lines:
        m_cau = re.match(r'^(Câu\s*\d+[:.]?)\s*(.*)$', ql, re.IGNORECASE)
        if m_cau:
            cau_prefix = m_cau.group(1).rstrip(':').rstrip('.') + ':'
            rest = m_cau.group(2).strip()
            if rest:
                body_parts.append(rest)
        else:
            body_parts.append(ql)
            
    question_full = (f'{cau_prefix} ' if cau_prefix else '') + ' '.join(body_parts)
    
    # Process options: Map to A, B, C, D
    options = []
    letters = ['A', 'B', 'C', 'D', 'E', 'F']
    opt_idx = 0
    
    for l in opt_raw_lines:
        cleaned = re.sub(r'^[\[\(][\s_xX✓✔oO0]?[\)\]]\s*', '', l)
        cleaned = re.sub(r'^[•\-\*▪▫]\s*', '', cleaned)
        cleaned = re.sub(r'^[oO0]\s+', '', cleaned)
        
        m = re.match(r'^([A-D])[\.\:\)]?\s*(.*)$', cleaned, re.IGNORECASE)
        if m:
            let = m.group(1).upper()
            txt = m.group(2).strip()
            options.append(f'{let}. {txt}')
            if let in letters:
                opt_idx = letters.index(let) + 1
        elif opt_idx < len(letters):
            let = letters[opt_idx]
            txt = re.sub(r'^\d+[\.\:\)]\s*', '', cleaned).strip()
            options.append(f'{let}. {txt}')
            opt_idx += 1
            
    result = [question_full] + options
    return '\n'.join(result)

print(smart_format_advanced(raw))
