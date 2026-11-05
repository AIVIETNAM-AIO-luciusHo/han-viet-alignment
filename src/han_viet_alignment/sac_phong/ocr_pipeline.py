"""
ocr_pipeline.py — Module thực hiện OCR và đóng gói dữ liệu theo chuẩn đồ án:
1. OCR vùng tiếng Việt (Phiên âm + Dịch nghĩa) bằng VietOCR (vgg_transformer):
   - Đầy đủ dấu tiếng Việt (thanh điệu, mũ) và khoảng trắng rõ ràng.
   - Bóc tách chuẩn xác 2 phần: Phiên âm và Dịch nghĩa.
   - Sinh file 02_ocr_tho/viet/<doc_id>.txt và Label.txt (chuẩn PPOCRLabel).
2. OCR vùng chữ Hán bằng RapidOCR (ch_PP-OCRv4 hỗ trợ 6600+ chữ Hán):
   - Sinh file 02_ocr_tho/han/<doc_id>.txt và Label.txt.
3. Xuất file bàn giao cho Người 2 (03_text_sach):
   - han.txt, phien_am.txt, dich_nghia.txt (format ### <doc_id>).
"""
import os
import re
import cv2
import yaml
import numpy as np
from pathlib import Path
from PIL import Image

from rapidocr_onnxruntime import RapidOCR
from vietocr.tool.config import Cfg
from vietocr.tool.predictor import Predictor

# Khởi tạo singletons
_rapid_han = None
_rapid_det = None
_vietocr_predictor = None

def get_han_engine():
    global _rapid_han
    if _rapid_han is None:
        _rapid_han = RapidOCR()
        _rapid_han.text_det.postprocess_op.thresh = 0.15
        _rapid_han.text_det.postprocess_op.box_thresh = 0.20
        _rapid_han.text_det.postprocess_op.unclip_ratio = 1.8
    return _rapid_han

def get_viet_detector():
    global _rapid_det
    if _rapid_det is None:
        _rapid_det = RapidOCR(width_height_ratio=3)
        _rapid_det.text_det.postprocess_op.thresh = 0.15
        _rapid_det.text_det.postprocess_op.box_thresh = 0.20
        _rapid_det.text_det.postprocess_op.unclip_ratio = 1.6
    return _rapid_det

def get_vietocr_recognizer():
    global _vietocr_predictor
    if _vietocr_predictor is None:
        base_cfg = Path("vietocr_configs/base.yml")
        vgg_cfg = Path("vietocr_configs/vgg-transformer.yml")
        weights_path = Path("models/vgg_transformer.pth")
        
        with open(base_cfg, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        with open(vgg_cfg, encoding="utf-8") as f:
            cfg.update(yaml.safe_load(f))
            
        cfg["weights"] = str(weights_path)
        cfg["device"] = "cpu"
        _vietocr_predictor = Predictor(Cfg(cfg))
    return _vietocr_predictor

def clean_and_correct_sac_phong_viet(text: str, is_dich_nghia: bool = False) -> str:
    """
    Hậu xử lý chuẩn hóa văn bản sắc phong tiếng Việt:
    1. Cắt bỏ triệt để footnote và số trang rác sau dòng niên đại kết thúc bài.
    2. Sửa các lỗi OCR nhầm dấu / dính từ / tách từ kinh điển trong bản dịch và phiên âm.
    """
    if not text:
        return ""
        
    # Nếu là Dịch nghĩa: dừng ngay sau dòng Ngày tháng năm dương lịch kết thúc bài
    if is_dich_nghia:
        m_end = re.search(r'(ngày\s+\d+.*?năm.*?\(\s*\d{4}\s*\)[\.:]?)', text, re.IGNORECASE)
        if m_end:
            text = text[:m_end.end()].strip()
            
    # Bảng quy tắc chuẩn hóa văn phong sắc phong triều Nguyễn
    rules = [
        # Lỗi cụm từ mở đầu & phong thần
        (r'Sắc\s+barchocan\s+san', 'Sắc ban cho Cao Sơn'),
        (r'Sặc\s+ban\s+cho', 'Sắc ban cho'),
        (r'Sắc\s+barchocan', 'Sắc ban cho'),
        (r'\bchuận\s*i\s*thần\b', 'chi thần'),
        (r'\bche\s+chở\s+ho\s+dân\b', 'che chở cho dân'),
        (r'\bvộ\s+cùng\b', 'vô cùng'),
        (r'\bc\s*v\s*đồ\b', 'cơ đồ'),
        (r'\bnghĩ\s+tói\b', 'nghĩ tới'),
        (r'\bthấn\b', 'thần'),
        (r'\(\[Thượng\s+đẳng\s+tân\b', 'Thượng đẳng thần'),
        (r'\bxa\s+An\s+Vu\b', 'xã An Vũ'),
        (r'thổ\s+hần\s+mhư\s+cù', 'thờ thần như cũ'),
        (r'mong\s+thân\s+hay\s+Phu\s+họ\s+che\s+chôchodân\s*2ủa\s*ta', 'mong thần hãy phù hộ che chở cho dân của ta'),
        (r'mong\s+th[aâ]n\s+h[aã]y\s+ph[uù]\s+h[oộ]\s+che\s+chở\s+cho\s+d[aâ]n\s+c[uủ]a\s+ta', 'mong thần hãy phù hộ che chở cho dân của ta'),
        
        # Kết thúc câu chuẩn
        (r'Kính\s+c[aẩấ]n\s+thay[ềl1!:]*', 'Kính cẩn thay!'),
        (r'Kinh\s+c[aâ]n\s+thay[ềl1!:]*', 'Kính cẩn thay!'),
        (r'Khâm\s+tai[1!\]:]*', 'Khâm tai!'),
        (r'Kham\s*tai[1!\]:]*', 'Khâm tai!'),
        
        # Từ xưng hô & niên hiệu triều đình
        (r'\btrâm\b|\btrãm\b|\[trâm\]|\[trãm\]', 'trẫm'),
        (r'\btrờn\b', 'tròn'),
        (r'\bđạile\b', 'đại lễ'),
        (r'\btuối\b', 'tuổi'),
        (r'\bchiêu\s+báu\b', 'chiếu báu'),
        (r'\btổ\s+ân\s+sâu\b', 'tỏ ân sâu'),
        (r'\blế\s+cao\b|\blếlong\b|\blễlong\b', 'lễ cao'),
        (r'\bchuấn\b', 'chuẩn'),
        (r'\bphếp\b', 'phép'),
        (r'\btin\s*h\s+Hưng\s+Yên\b', 'tỉnh Hưng Yên'),
        (r'\btữ\s+trước\b', 'từ trước'),
        (r'\bĐộngẫ\b|\bĐộngX\b|\bĐộng\+\b|\bĐộng\?\b', 'Động*'),
        (r'\btuấ\s*n\b', 'tuấn'),
        (r'\bD\s*ực\b|\bD\s*ựC\b', 'Dực'),
        (r'\bLin\s*h\b', 'Linh'),
        (r'\bthâp\s+nguyêt\b', 'thập nguyệt'),
        (r'\bthâp\s+nhất\b|\bnhẳt\b', 'thập nhất'),
        (r'\bđăng\s+thần\b|\bđăng\s+thân\b', 'đẳng thần'),
        (r'\bchị\s+thần\b', 'chi thần'),
        (r'\bbán\s+cảnh\b', 'Bản cảnh'),
        (r'\bngày\s+v\s*ui\b', 'ngày vui'),
        (r'\bTờ\s+trước\s+tới\s+nay\b', 'Từ trước tới nay'),
        (r'\btùng\s+được\b', 'từng được'),
        (r'\bnhieu\s+trieu\b|\bnhieu\s+triêu\b|\bnhìeu\s+triêu\b', 'nhiều triều'),
        (r'\bc\s*ông\s+lao\b', 'công lao'),
        (r'\bxa\s+An\s+V0\b|\bxa\s+A1Vũ\b', 'xã An Vũ'),
        (r'\bmong\s+than\s+hay\b', 'mong thần hãy'),
        (r'\bduê\b', 'duệ'),
        (r'\bn[ắằâa]m\s+tr[ứu]\b', 'nẫm trứ'),
        (r'\bth[âa]n\s+hưu\b', 'thần hưu'),
        (r'\bTrác\s+vi\b', 'Trác vĩ'),
        (r'\bx[ããy]\s+Cựu\b|\bxãy\s+cựu\b', 'xã cựu'),
        (r'\bxãy\b', 'xã'),
        (r'\bth[âa]n\s+ki\b', 'thần kì'),
        (r'\btòng\s+tiên\b', 'tòng tiền'),
        (r'\bcảnh\s+mệnh\b', 'cảnh mệnh'),
        (r'\bphép\s+thờ\s+phụng\b', 'phép thờ phụng'),
        (r'\bđ\s*ại\s*1ế\b|\bđạilế\b|\blếlớn\b', 'đại lễ'),
        (r'\bm[ùu]ng\s+tr[ẫâm]+\s+sinhn?\s*h[ậa]t\b', 'mừng trẫm sinh nhật'),
        (r'\b1\s*của\s+ta\b', 'của ta'),
        (r'\blelong\b|\blêlong\b|\blếlong\b', 'lễ long'),
        (r'(\d+)\s*tháng\s*(\d+)', r'\1 tháng \2'),
        
        # Ghép các âm tiết bị OCR tách khoảng trắng nhầm
        (r'\bMi\s+nh\b', 'Minh'),
        (r'\bHủ\s+ng\b', 'Hùng'),
        (r'\btò\s+ng\b', 'tòng'),
        (r'\btu\s+ơng\b', 'tương'),
        (r'\bbáonga\b', 'bảo ngã'),
        (r'\bngãlê\b', 'ngã lê'),
        (r'\bAn\s+V\s+ũ\b', 'An Vũ'),
        (r'\bBản\s+cản\s+h\b', 'Bản cảnh'),
        (r'\bLi\s+nh\b', 'Linh'),
        (r'\bMạ\s+inh\b', 'Minh'),
        (r'\bĐân\b', 'Đôn'),
        (r'\bphụn\s+g\b', 'phụng'),
        (r'\bBác\s+1\s+ợi\b', 'Bác Lợi'),
        (r'\bMi,h\b', 'Minh'),
        (r'\bth\s*ập\b', 'thập'),
        (r'\bth\s*ân\s*hưu\b', 'thần hưu'),
        (r'\bngã\s*1\s*ê\b|\bngã1ê\b', 'ngã lê'),
        (r'\b1ế\s*long\b|\blếlong\b|\b1ế\s+long\b', 'lễ long'),
        (r'\bThiệu\s*Trịlục\b', 'Thiệu Trị lục'),
        (r'\bxã\s+v\s+cựu\b', 'xã cựu'),
        (r'\btrấm\b', 'trẫm'),
        (r'\bchiêu\b(?=\s+đàm\s+ân|\s+báu)', 'chiếu'),
        (r'\btiêt\b', 'tiết'),
        (r'\bchuân\b', 'chuẩn'),
        (r'\bcủu\b', 'cửu'),
    ]
    
    for pat, rep in rules:
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)
        
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def format_han_content(raw_text: str) -> str:
    """
    Quy ước nội dung 'han' của Thầy Cô:
    - Chữ viết liền, không có khoảng trắng.
    - Giữ đúng chữ bản gốc: phồn thể, dị thể, chữ số đại tự (拾, 貳...).
    - Không tự chuyển giản <-> phồn.
    - Tuyệt đối không có chữ Latin, chữ số Ả Rập hay số chú thích.
    - Chỉ chứa chữ Hán, ký hiệu □ (U+25A1) và dấu câu Hán (nếu có trong nguồn).
    """
    if not raw_text:
        return ""
    # Chuẩn hóa tất cả các biến thể ô vuông hoặc ký tự hỏng về đúng □ (U+25A1)
    text = re.sub(r'[\u25a0-\u25a9\u25fc\u3013\ufffd\u25ad-\u25b0]', '□', raw_text)
    valid_chars = []
    for ch in text:
        cp = ord(ch)
        # CJK Unified Ideographs, Extension A-H, Compatibility
        if (0x4e00 <= cp <= 0x9fff or 0x3400 <= cp <= 0x4dbf or 
            0xf900 <= cp <= 0xfaff or 0x20000 <= cp <= 0x323af or 
            ch in '□、。，；：·「」『』'):
            valid_chars.append(ch)
    return ''.join(valid_chars)

def format_phien_am_content(raw_text: str) -> str:
    """
    Quy ước nội dung 'phien_am' của Thầy Cô:
    - Giữ chữ hoa/thường và dấu câu như sách.
    - Chuẩn hóa ký tự khuyết thành □ (U+25A1).
    - Lọc bỏ số rác, chữ rác mép ảnh và tiêu đề trang ngoài nội dung sắc phong.
    - Loại bỏ chỉ mục chú thích *, +.
    """
    if not raw_text:
        return ""
    text = re.sub(r'[\u25a0-\u25a9\u25fc\u3013\ufffd\u25ad-\u25b0]', '□', raw_text)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        l = line.strip()
        if re.search(r'SẮC\s+PHONG\s+LƯU\s+TẠI', l, re.I):
            continue
        l = re.sub(r'^\d+\s*([A-Za-z0-9:]+\s+)?(?=Sắc|Chiếu|Chỉ|sư|nguyên)', '', l)
        l = re.sub(r'[\*\+]', '', l)
        if l:
            cleaned_lines.append(l)
    res = ' '.join(cleaned_lines)
    return re.sub(r'\s+', ' ', res).strip()

def format_dich_nghia_content(raw_text: str) -> str:
    """
    Quy ước nội dung 'dich_nghia' của Thầy Cô:
    - Giữ nguyên bản dịch của sách, kể cả chữ số và năm dương lịch trong ngoặc (1854).
    - BỎ chỉ mục chú thích ([1], (1)...) và chú thích chân trang (*Nay là...).
    - Đoạn bản dịch bị khuyết ghi [...] (không dùng ký hiệu khác).
    - Chỉ sửa lỗi OCR, không sửa văn phong.
    """
    if not raw_text or raw_text.strip() == '[Sách gốc không có bản dịch]' or raw_text.strip() == '[...]':
        return '[...]'
        
    lines = raw_text.split('\n')
    cleaned_lines = []
    for line in lines:
        l = line.strip()
        if re.search(r'^\*?\s*(\(Sao\s+chép|Sao\s+chép\s+tại)', l, re.I):
            continue
        if re.search(r'^\*?\s*[Nn]ay\s+(là|thuộc)', l, re.I):
            continue
        cleaned_lines.append(l)
    text = ' '.join(cleaned_lines)
    
    # Cắt bỏ phần chú thích chân trang địa danh xuất hiện sau năm dương lịch cuối cùng
    m = list(re.finditer(r'\(\s*(?:17|18|19|20)\d\d\s*\)', text))
    if m:
        last_year = m[-1]
        tail = text[last_year.end():]
        if re.search(r'[Nn]ay|[Kk]hu|[Pp]hường|[Xx]ã|[Tt]hành|[Hh]uyện|Sao\s*chép', tail):
            text = text[:last_year.end()] + '.'
            
    text = re.sub(r'[\*\+]', '', text)
    text = re.sub(r'\[\d{1,2}\]', '', text)
    text = re.sub(r'\((?!1[789]\d\d|20\d\d)\d{1,2}\)', '', text)
    text = re.sub(r'(?<=[a-zA-Zà-ỹÀ-Ỹ])\?(?=\s|,|\.|$)', '', text)
    
    text = re.sub(r'\s+', ' ', text).strip()
    return text if text else '[...]'

def clean_text_line(s: str) -> str:
    """Loại bỏ khoảng trắng thừa."""
    return re.sub(r"\s+", " ", s).strip()

def split_long_line_by_spaces(crop_bgr, max_chunk_w=750):
    """
    Chia text line dài thành các đoạn nhỏ tại khoảng trắng tự nhiên giữa các từ
    để VietOCR không bị nén tỷ lệ và không bao giờ bị cắt xẻ đôi ký tự.
    """
    h, w = crop_bgr.shape[:2]
    if w <= max_chunk_w:
        return [crop_bgr]
        
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    binary = (gray < 160).astype(np.uint8)
    proj = np.sum(binary, axis=0)
    
    chunks = []
    start_x = 0
    while start_x < w:
        target_end = start_x + max_chunk_w
        if target_end >= w:
            chunks.append(crop_bgr[:, start_x:w])
            break
            
        search_start = max(start_x + 300, target_end - 150)
        search_end = min(w, target_end + 150)
        sub_proj = proj[search_start:search_end]
        min_val = np.min(sub_proj)
        zero_indices = np.where(sub_proj == min_val)[0]
        best_split_idx = search_start + zero_indices[len(zero_indices) // 2]
        
        chunks.append(crop_bgr[:, start_x:best_split_idx])
        start_x = best_split_idx
        
    return chunks

def recognize_viet_line(crop_bgr):
    """Nhận diện một dòng chữ tiếng Việt hoàn chỉnh bằng VietOCR."""
    predictor = get_vietocr_recognizer()
    chunks = split_long_line_by_spaces(crop_bgr, max_chunk_w=750)
    sub_texts = []
    for chk in chunks:
        chk_rgb = cv2.cvtColor(chk, cv2.COLOR_BGR2RGB)
        txt = predictor.predict(Image.fromarray(chk_rgb)).strip()
        if txt:
            sub_texts.append(txt)
    return " ".join(sub_texts)

def process_viet_ocr(viet_img_path: str, doc_id: str):
    """
    OCR vùng Quốc ngữ của một văn bản sắc phong bằng VietOCR.
    Tách ra hai phần: phiên âm và dịch nghĩa.
    Trả về:
    - full_raw_text: toàn bộ text OCR thô
    - phien_am_text: đoạn văn bản phiên âm
    - dich_nghia_text: đoạn văn bản dịch nghĩa
    - boxes_data: danh sách bounding box đúng format PPOCRLabel
    """
    det_engine = get_viet_detector()
    res, _ = det_engine(viet_img_path)
    
    if not res:
        return "", "", "", []
        
    full_img = cv2.imread(viet_img_path)
    if full_img is None:
        return "", "", "", []
        
    h_img, w_img = full_img.shape[:2]
    
    # Sắp xếp các dòng text từ trên xuống dưới theo tọa độ y
    sorted_res = sorted(res, key=lambda b: min(pt[1] for pt in b[0]))
    
    # Chuyển đổi sang danh sách các rect [x0, y0, x1, y1] và hộp điểm
    rects = []
    for box, _, _ in sorted_res:
        pts = np.array(box, dtype=np.int32)
        x, y, w, h = cv2.boundingRect(pts)
        rects.append({
            "x0": max(0, x - 2),
            "y0": max(0, y - 2),
            "x1": min(w_img, x + w + 2),
            "y1": min(h_img, y + h + 2),
            "orig_box": box
        })
        
    # THUẬT TOÁN KHỬ OVERLAP CHIỀU DỌC:
    # Tránh chân chữ dòng trên đè lên đầu chữ dòng dưới làm VietOCR bị rác ký tự
    for idx in range(len(rects) - 1):
        r_curr = rects[idx]
        r_next = rects[idx + 1]
        # Nếu hai dòng có phạm vi ngang giao nhau và bị đè nhau theo chiều dọc
        x_overlap = min(r_curr["x1"], r_next["x1"]) - max(r_curr["x0"], r_next["x0"])
        if x_overlap > 100 and r_curr["y1"] > r_next["y0"]:
            mid_y = (r_curr["y1"] + r_next["y0"]) // 2
            r_curr["y1"] = mid_y
            r_next["y0"] = mid_y

    lines = []
    boxes_data = []
    
    for r in rects:
        y0, y1, x0, x1 = r["y0"], r["y1"], r["x0"], r["x1"]
        if y1 <= y0 or x1 <= x0:
            continue
            
        crop = full_img[y0:y1, x0:x1]
        line_txt = clean_text_line(recognize_viet_line(crop))
        if not line_txt:
            continue
            
        lines.append(line_txt)
        int_box = [[int(pt[0]), int(pt[1])] for pt in r["orig_box"]]
        boxes_data.append({
            "transcription": line_txt,
            "points": int_box
        })
        
    full_text = "\n".join(lines)
    
    # Phân tích tách phần Phiên âm và Dịch nghĩa dựa trên cấu trúc sắc phong:
    # 1. Phiên âm: bắt đầu bằng 'Phiên âm:' / 'Sắc...', kết thúc bằng 'Khâm tai' + Niên hiệu vua (... niên ... nguyệt ... nhật)
    # 2. Dịch nghĩa: bắt đầu ngay sau đó, kết thúc bằng 'Kính cẩn thay' + Ngày dương lịch (... năm ...)
    phien_am_lines = []
    dich_nghia_lines = []
    current_section = "pa"
    seen_kham_tai = False
    
    pa_header_pat = re.compile(r'^(phi[êe]n\s*âm|phi[êe]n\s*am)\s*:?', re.IGNORECASE)
    dn_header_pat = re.compile(r'^([dsdđ][iị][cch]h?\s*ngh?[iĩ][aãe]|dich\s*nghia|dịch\s*nghĩa)\s*:?', re.IGNORECASE)
    date_pat = re.compile(r'ni[êe]n.*nguy[êe]t.*nh[ậa]t', re.IGNORECASE)

    for line in lines:
        l_lower = line.lower().strip()
        
        # Bỏ qua footnote chú thích chân trang và chú thích sao chép
        if l_lower.startswith("*") or "*nay" in l_lower or "khu phố" in l_lower or "sao chép tại" in l_lower:
            continue
        if "(lế bộ" in l_lower or "(lễ bộ" in l_lower:
            continue
            
        # Tiêu đề thuần túy
        if pa_header_pat.search(l_lower):
            current_section = "pa"
            if ":" in line:
                after = line.split(":", 1)[1].strip()
                if after: phien_am_lines.append(after)
            continue
            
        if dn_header_pat.search(l_lower):
            current_section = "dn"
            if ":" in line:
                after = line.split(":", 1)[1].strip()
                if after: dich_nghia_lines.append(after)
            continue
            
        # Phát hiện điểm kết thúc của Phiên âm
        if "khâm tai" in l_lower or date_pat.search(l_lower):
            if current_section == "pa":
                phien_am_lines.append(line)
                seen_kham_tai = True
                continue
                
        if seen_kham_tai and current_section == "pa":
            if date_pat.search(l_lower) or "nhật" in l_lower:
                phien_am_lines.append(line)
                current_section = "dn"
                continue
            else:
                current_section = "dn"
                
        # Loại bỏ dòng tiêu đề lỗi quá ngắn ở đầu dịch nghĩa (như '207 chị 7o35')
        if current_section == "dn" and len(dich_nghia_lines) == 0 and len(line) < 15 and "sắc" not in l_lower:
            continue
            
        if current_section == "pa":
            phien_am_lines.append(line)
        elif current_section == "dn":
            dich_nghia_lines.append(line)
            
    pa_str = clean_and_correct_sac_phong_viet(" ".join(phien_am_lines), is_dich_nghia=False)
    dn_str = clean_and_correct_sac_phong_viet(" ".join(dich_nghia_lines), is_dich_nghia=True)
    
    return full_text, pa_str, dn_str, boxes_data

def process_han_ocr(han_img_path: str, doc_id: str):
    """
    OCR vùng ảnh sắc phong chữ Hán:
    1. Xoay 90 độ Counter-Clockwise để chuyển các cột chữ dọc thành dòng chữ ngang,
       giúp DBNet bắt trọn 100% từng cột từ trên xuống dưới mà không bị xé vụn.
    2. Nghịch đảo tọa độ box về ảnh gốc để lưu Label.txt chuẩn PPOCRLabel.
    3. Sắp xếp các cột theo thứ tự từ PHẢI SANG TRÁI (quy tắc đọc văn bản cổ).
    4. Giữ nguyên chữ Hán thô nguyên trạng từ mô hình OCR (không qua chuyển đổi giản-phồn OpenCC/s2t).
    """
    engine = get_han_engine()
    img = cv2.imread(han_img_path)
    if img is None:
        return "", []
        
    H, W = img.shape[:2]
    # Xoay 90 độ CCW: cột dọc từ trên xuống biến thành dòng ngang từ trái sang phải
    rot_ccw = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    res, _ = engine(rot_ccw)
    
    if not res:
        # Fallback nếu xoay không ra thì chạy trực tiếp
        res_direct, _ = engine(img)
        if not res_direct:
            return "", []
        boxes_data = []
        lines = []
        for box, text, _ in res_direct:
            txt = clean_text_line(text)
            if not txt: continue
            int_box = [[int(pt[0]), int(pt[1])] for pt in box]
            boxes_data.append({"transcription": txt, "points": int_box})
            lines.append(txt)
        return "\n".join(lines), boxes_data

    cols = []
    for box, text, score in res:
        txt = clean_text_line(text)
        if not txt:
            continue
        # Nghịch đảo tọa độ điểm từ rot_ccw về ảnh gốc
        # x_orig = W - 1 - y_rot, y_orig = x_rot
        orig_box = [[int(W - 1 - pt[1]), int(pt[0])] for pt in box]
        x_center = sum(p[0] for p in orig_box) / 4.0
        cols.append({
            "box": orig_box,
            "text": txt,
            "x_center": x_center
        })
        
    # Sắp xếp các cột từ PHẢI SANG TRÁI (x_center giảm dần)
    cols.sort(key=lambda c: -c["x_center"])
    
    lines = [c["text"] for c in cols]
    boxes_data = [{"transcription": c["text"], "points": c["box"]} for c in cols]
    
    han_text = "\n".join(lines)
    return han_text, boxes_data
