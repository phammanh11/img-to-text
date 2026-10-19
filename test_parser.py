import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

def smart_format_quiz(ocr_text):
    if not ocr_text:
        return ''
    raw_lines = [l.strip() for l in ocr_text.splitlines() if l.strip()]
    
    # Junk filters (status bar, timers, page numbers, navigation)
    time_pat = re.compile(r'^\d{1,2}:\d{2}(:\d{2})?$')
    battery_pat = re.compile(r'^\d{1,3}%?$')
    page_pat = re.compile(r'^(\d+[\s/]+\d+|<\s*\d+[\s/]+\d+\s*>)$')
    junk_exact = {'<', '>', '«', '»', 'câu hỏi', 'trả lời:', 'trả lời', 'đáp án:', 'đáp án', 'bài kiểm tra'}
    
    filtered = []
    for l in raw_lines:
        lower = l.lower()
        if lower in junk_exact:
            continue
        if time_pat.match(l) or (battery_pat.match(l) and len(l) <= 3) or page_pat.match(l):
            continue
        if lower.startswith(('kiểm tra tuần', 'thời gian còn lại', 'thời gian làm bài', 'câu hỏi ')):
            if re.search(r'\d+\s*/\s*\d+', l):
                continue
            if lower in ('kiểm tra tuần', 'câu hỏi'):
                continue
        # Strip leading checkbox or bullet glyphs like [ ], ( ), *, -, •, ▪
        cleaned_line = re.sub(r'^[\[\(][\s_xX✓✔]?[\]\)]\s*', '', l)
        cleaned_line = re.sub(r'^[•\-\*▪▫]\s*', '', cleaned_line)
        if cleaned_line.strip():
            filtered.append(cleaned_line.strip())
            
    # Reassemble question and options
    result = []
    i = 0
    option_pat = re.compile(r'^([A-H])[\.\:\)]\s*(.*)$', re.IGNORECASE)
    
    while i < len(filtered):
        line = filtered[i]
        
        # Check if line is 'Câu XX:' or 'Câu XX' alone
        m_cau = re.match(r'^(Câu\s*\d+[:.]?)\s*$', line, re.IGNORECASE)
        if m_cau and i + 1 < len(filtered):
            next_line = filtered[i+1]
            if not option_pat.match(next_line):
                # Ensure colon
                prefix = m_cau.group(1).rstrip(':').rstrip('.') + ':'
                result.append(f'{prefix} {next_line}')
                i += 2
                continue
                
        # Standardize option line: A. Text
        m_opt = option_pat.match(line)
        if m_opt:
            letter = m_opt.group(1).upper()
            content = m_opt.group(2).strip()
            result.append(f'{letter}. {content}')
            i += 1
            continue
            
        result.append(line)
        i += 1
        
    return '\n'.join(result)

sample = '''
20:05
59
Kiểm tra tuần
Câu 14:
12:42
Ưu điểm của ảnh mức xám so với ảnh màu bao gồm:
(chọn 3 đáp án đúng)
Hãy chọn 3 đáp án đúng nhất !
Trả lời:
[ ] A.  Hiển thị được nhiều màu sắc sống động hơn
[ ] B.  Tốn ít bộ nhớ hơn
[ ] C.  Dễ xử lý hơn trong các thuật toán cơ bản
[ ] D.  Kích thước tệp nhỏ hơn
<
Câu hỏi
14/15
'''

output = smart_format_quiz(sample)
print(output)
