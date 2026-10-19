import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

def parse_quiz_robust(ocr_text):
    if not ocr_text:
        return {"smart_text": "", "question_title": "", "instruction": "", "options": []}

    raw_lines = [l.strip() for l in ocr_text.splitlines() if l.strip()]

    # 1. Tìm vị trí dòng bắt đầu chứa "Câu" hoặc "Câu [số]"
    # Loại bỏ hoàn toàn mọi nội dung phía trên "Câu" (như 'Kiểm tra tuần', đồng hồ, pin, môn học...)
    start_idx = 0
    for idx, l in enumerate(raw_lines):
        if re.search(r'^\s*Câu\s*(\d+|[A-Z0-9]+|:)', l, re.IGNORECASE):
            start_idx = idx
            break

    # Cắt chỉ lấy từ dòng "Câu" trở đi
    lines_from_cau = raw_lines[start_idx:]

    # 2. Lọc bỏ các dòng rác nằm bên dưới "Câu"
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

    # Tách phần Câu hỏi & Các đáp án
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

        m_cau = re.match(r'^(Câu\s*\d+[:.]?)\s*(.*)$', l, re.IGNORECASE)
        if m_cau:
            cau_prefix = m_cau.group(1).rstrip(':').rstrip('.') + ':'
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

    smart_lines = []
    if full_q:
        smart_lines.append(full_q)
    for inst in instructions:
        smart_lines.append(inst)
    for opt in options:
        smart_lines.append(f"{opt['key']}. {opt['text']}")

    smart_text = "\n".join(smart_lines)
    return {
        "smart_text": smart_text,
        "question_title": full_q,
        "instruction": "\n".join(instructions),
        "options": options
    }

# Test 1: Image 1
sample_1 = '''20:05
59
Kiểm tra tuần
Câu 14:
12:42
Ưu điểm của ảnh mức xám so với ảnh màu bao gồm:
(chọn 3 đáp án đúng)
Hãy chọn 3 đáp án đúng nhất !
Trả lời:
A. Hiển thị được nhiều màu sắc sống động hơn
B. Tốn ít bộ nhớ hơn
C. Dễ xử lý hơn trong các thuật toán cơ bản
D. Kích thước tệp nhỏ hơn
<
Câu hỏi
14/15'''

print("=== TEST 1 ===")
print(parse_quiz_robust(sample_1)['smart_text'])

# Test 2: Câu 6
sample_2 = '''19:29
Kiểm tra tuần
14:21
Câu 6
Học sâu (Deep Learning) khác biệt với học máy truyền thống
ở điểm nào sau đây?
Trà 10%
A. Để triển khai hơn trong mọi tình huống
B. Không dùng mạng neuron
C
Dùng mang neuron nhiều tầng để học đặc trưng
phức tạp
D. Không cần dữ liệu
Câu hỏi
6/15
>'''

print("\n=== TEST 2 ===")
print(parse_quiz_robust(sample_2)['smart_text'])
