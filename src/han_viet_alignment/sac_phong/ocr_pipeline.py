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
        cur = Path(__file__).resolve()
        project_root = None
        for p in [cur] + list(cur.parents):
            if (p / ".git").exists() or (p / "guideline").exists():
                project_root = p
                break
        if project_root is None:
            project_root = Path.cwd()

        v6_dir = project_root / "models" / "ppocrv6"
        v6_det = v6_dir / "PP-OCRv6_det_medium.onnx"
        v6_rec = v6_dir / "PP-OCRv6_rec_medium.onnx"

        # Tự động tải nếu máy thành viên khác chưa có model v6
        if not (v6_det.exists() and v6_rec.exists()):
            try:
                print("[*] Đang tải mô hình Paddle v6 (PP-OCRv6 Medium) từ HuggingFace...")
                v6_dir.mkdir(parents=True, exist_ok=True)
                from huggingface_hub import hf_hub_download
                hf_hub_download(repo_id="haotruong-hitlab/pp-ocrv6-medium-onnx", filename="PP-OCRv6_det_medium.onnx", local_dir=str(v6_dir))
                hf_hub_download(repo_id="haotruong-hitlab/pp-ocrv6-medium-onnx", filename="PP-OCRv6_rec_medium.onnx", local_dir=str(v6_dir))
            except Exception as e:
                print(f"[!] Không thể tải tự động model v6: {e}")

        if v6_det.exists() and v6_rec.exists():
            print("[*] Đang khởi tạo OCR chữ Hán với mô hình Paddle v6 (PP-OCRv6 Medium)...")
            _rapid_han = RapidOCR(det_model_path=str(v6_det), rec_model_path=str(v6_rec))
        else:
            print("[*] Khởi tạo RapidOCR mặc định...")
            _rapid_han = RapidOCR()

        _rapid_han.text_det.postprocess_op.thresh = 0.15
        _rapid_han.text_det.postprocess_op.box_thresh = 0.20
        _rapid_han.text_det.postprocess_op.unclip_ratio = 1.8
        # RapidOCR bỏ cả dòng có điểm < text_score. Đã đo trên R1001.001–007 qua đường xử lý thật,
        # chấm như kiem_tra_du_lieu.py: 0.5 -> 201/423 (47,5%); 0.1 -> 203/467 (43,5%);
        # 0.1 + lọc dòng rác (alignment/han_filter.py) -> 201/450 (44,7%). Hạ ngưỡng chủ yếu thêm chữ sai
        # nên giữ 0.5. Với 0.5, bộ lọc han_filter không loại gì (chỉ xét dòng điểm < 0.5).
        _rapid_han.text_score = 0.5
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
        
    # Nếu là Dịch nghĩa: dừng ngay sau dòng Ngày tháng năm dương lịch kết thúc bài cuối cùng
    # (tránh cắt nhầm các mục "Phụng sao..." liệt kê nhiều niên hiệu nối tiếp trong cùng bài)
    if is_dich_nghia:
        m_all = list(re.finditer(
            r'ngày\s+\d+[^()]{0,65}?\(\s*(?:17|18|19|20)\d\d\s*\)[\.:]?',
            text,
            re.IGNORECASE,
        ))
        if m_all:
            m_end = m_all[-1]
            tail = text[m_end.end():].strip()
            if not re.search(r'\bban\s*t[ặa]ng|\bm[ĩi]\s*t[ựư]|\bchu[ẩa]n\s*cho|\bs[ắa]c\s*phong', tail[:100], re.IGNORECASE):
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

def _imread_bgr(img_path: str):
    """Đọc ảnh BGR an toàn cả với đường dẫn chứa ký tự Unicode trên Windows."""
    p = Path(img_path)
    if not p.exists():
        return None
    data = np.fromfile(str(p), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def recognize_viet_line(crop_bgr):
    """Nhận diện một dòng chữ tiếng Việt hoàn chỉnh bằng VietOCR."""
    if crop_bgr is None or crop_bgr.size == 0 or crop_bgr.shape[1] < 4 or crop_bgr.shape[0] < 4:
        return ""
    predictor = get_vietocr_recognizer()
    chunks = split_long_line_by_spaces(crop_bgr, max_chunk_w=750)
    sub_texts = []
    for chk in chunks:
        if chk.shape[1] < 4 or chk.shape[0] < 4:
            continue
        chk_gray = cv2.cvtColor(chk, cv2.COLOR_BGR2GRAY)
        if int(np.sum(chk_gray < 175)) < 8:
            continue
        chk_rgb = cv2.cvtColor(chk, cv2.COLOR_BGR2RGB)
        txt = predictor.predict(Image.fromarray(chk_rgb)).strip()
        if txt:
            sub_texts.append(txt)
    return " ".join(sub_texts)


def _estimate_skew_angle(mask: np.ndarray) -> float:
    """Ước lượng góc nghiêng nhỏ (-2.0..+2.0 độ) bằng phương sai projection ngang."""
    h_m, w_m = mask.shape
    if h_m < 40 or w_m < 160:
        return 0.0
    small = cv2.resize(mask, (max(40, w_m // 4), max(20, h_m // 4)), interpolation=cv2.INTER_NEAREST)
    sh, sw = small.shape
    # Bỏ rìa 4px để viền cắt ảnh không chi phối phương sai
    if sh > 10:
        small[:3, :] = 0
        small[-3:, :] = 0
    center = (sw / 2.0, sh / 2.0)

    best_a, best_var = 0.0, -1.0
    for angle in np.linspace(-2.0, 2.0, 21):
        mat = cv2.getRotationMatrix2D(center, float(angle), 1.0)
        rot = cv2.warpAffine(small, mat, (sw, sh), flags=cv2.INTER_NEAREST)
        var = float(np.var(rot.sum(axis=1)))
        if var > best_var:
            best_var = var
            best_a = float(angle)

    base = best_a
    for angle in np.linspace(base - 0.2, base + 0.2, 11):
        mat = cv2.getRotationMatrix2D(center, float(angle), 1.0)
        rot = cv2.warpAffine(small, mat, (sw, sh), flags=cv2.INTER_NEAREST)
        var = float(np.var(rot.sum(axis=1)))
        if var > best_var:
            best_var = var
            best_a = float(angle)

    return best_a


def _segment_viet_lines_projection(full_img: np.ndarray, return_work_img: bool = False):
    """
    Phân tách từng dòng chữ tiếng Việt bằng Peak-Valley Projection (có tự động
    nắn thẳng góc nghiêng nhỏ trên khổ rộng Layout A w > 1800px), loại bỏ viền
    cắt, thước kẻ ngang và đốm hằn trang chống VietOCR bịa chữ.
    """
    h_img, w_img = full_img.shape[:2]
    gray0 = cv2.cvtColor(full_img, cv2.COLOR_BGR2GRAY)
    bg0 = cv2.GaussianBlur(gray0, (51, 51), 0)
    diff0 = bg0.astype(np.int16) - gray0.astype(np.int16)
    mask0 = (diff0 > 48).astype(np.uint8)

    angle = _estimate_skew_angle(mask0) if w_img > 1800 else 0.0
    inv_mat = None
    if abs(angle) >= 0.12:
        center_full = (w_img / 2.0, h_img / 2.0)
        rot_mat = cv2.getRotationMatrix2D(center_full, angle, 1.0)
        bg_color = tuple(int(c) for c in np.median(full_img, axis=(0, 1)))
        work_img = cv2.warpAffine(
            full_img,
            rot_mat,
            (w_img, h_img),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=bg_color,
        )
        inv_mat = cv2.invertAffineTransform(rot_mat)
        gray = cv2.cvtColor(work_img, cv2.COLOR_BGR2GRAY)
        bg = cv2.GaussianBlur(gray, (51, 51), 0)
        diff = bg.astype(np.int16) - gray.astype(np.int16)
    else:
        work_img = full_img
        gray = gray0
        diff = diff0

    # Ngưỡng mực in rõ (loại bỏ vết mực hằn mặt sau)
    mask_text = (diff > 48).astype(np.uint8)
    mask_strong = (diff > 56).astype(np.uint8)

    # Xóa nhiễu viền ngoài cùng do cắt trang
    pad_y = min(8, h_img // 10)
    pad_x = min(6, w_img // 10)
    if pad_y > 0:
        mask_text[:pad_y, :] = 0
        mask_text[-pad_y:, :] = 0
        mask_strong[:pad_y, :] = 0
        mask_strong[-pad_y:, :] = 0
    if pad_x > 0:
        mask_text[:, :pad_x] = 0
        mask_text[:, -pad_x:] = 0
        mask_strong[:, :pad_x] = 0
        mask_strong[:, -pad_x:] = 0

    # Xóa đường kẻ ngang chú thích chân trang bằng MorphOpen (150x1)
    if w_img > 160:
        horiz_k = cv2.getStructuringElement(cv2.MORPH_RECT, (150, 1))
        h_lines = cv2.morphologyEx(mask_text, cv2.MORPH_OPEN, horiz_k)
        mask_clean = cv2.subtract(mask_text, h_lines)
        h_lines_s = cv2.morphologyEx(mask_strong, cv2.MORPH_OPEN, horiz_k)
        mask_strong_clean = cv2.subtract(mask_strong, h_lines_s)
    else:
        mask_clean = mask_text
        mask_strong_clean = mask_strong

    row_proj = mask_clean.sum(axis=1).astype(np.float32)
    kernel = np.array([0.03, 0.08, 0.18, 0.42, 0.18, 0.08, 0.03], dtype=np.float32)
    smooth = np.convolve(row_proj, kernel, mode="same")

    # Giữ cả peak yếu của tiêu đề ngắn ('Phiên âm:', 'Cố sắc!', 'Dịch nghĩa:')
    cand_peaks = []
    for y in range(1, h_img - 1):
        if smooth[y] >= 6.0 and smooth[y] >= smooth[y - 1] and smooth[y] >= smooth[y + 1]:
            cand_peaks.append((float(smooth[y]), y))

    # NMS giữ các dòng cách nhau tối thiểu 22px
    cand_peaks.sort(reverse=True)
    peaks = []
    for _, y in cand_peaks:
        if all(abs(y - py) >= 22 for py in peaks):
            peaks.append(y)
    peaks.sort()

    if not peaks:
        return ([], work_img) if return_work_img else []

    rects = []
    max_half_h = 28
    for i, pk in enumerate(peaks):
        if i == 0:
            limit_top = max(0, pk - max_half_h)
        else:
            prev_pk = peaks[i - 1]
            v_top = prev_pk + int(np.argmin(smooth[prev_pk : pk + 1]))
            limit_top = max(v_top, pk - max_half_h)

        if i == len(peaks) - 1:
            limit_bot = min(h_img, pk + max_half_h)
        else:
            next_pk = peaks[i + 1]
            v_bot = pk + int(np.argmin(smooth[pk : next_pk + 1]))
            limit_bot = min(v_bot + 1, pk + max_half_h)

        band_proj = row_proj[limit_top:limit_bot]
        active_y = np.where(band_proj >= 1.5)[0]
        if len(active_y) == 0:
            continue

        raw_span_h = int(active_y[-1] - active_y[0] + 1)
        if raw_span_h < 10 or float(band_proj.sum()) < 80.0:
            continue

        y0 = max(limit_top, limit_top + int(active_y[0]) - 3)
        y1 = min(limit_bot, limit_top + int(active_y[-1]) + 4)

        col_proj = mask_strong_clean[y0:y1, :].sum(axis=0)
        dark_cols = np.where(col_proj > 0)[0]
        if len(dark_cols) == 0:
            continue

        # Nhóm các cột có mực đậm theo khoảng hở <= 45px để không kéo đốm xa vào dòng ngắn
        clusters = []
        c_start = int(dark_cols[0])
        c_prev = int(dark_cols[0])
        for cx in dark_cols[1:]:
            cx_i = int(cx)
            if cx_i - c_prev > 45:
                clusters.append((c_start, c_prev))
                c_start = cx_i
            c_prev = cx_i
        clusters.append((c_start, c_prev))

        band_diff = diff[y0:y1, :]
        band_gray = gray[y0:y1, :]
        band_h = max(1, y1 - y0)
        valid_sub_rects = []
        for s_x, e_x in clusters:
            seg_w = e_x - s_x + 1
            seg_ink = int(col_proj[s_x : e_x + 1].sum())
            very_dark = int((band_diff[:, s_x : e_x + 1] > 75).sum())
            seg_gray = band_gray[:, s_x : e_x + 1]
            col_dark = (seg_gray < 160).sum(axis=0)
            fill = float((seg_gray < 150).sum()) / float(seg_w * band_h)
            zero_ratio = float((col_dark == 0).sum()) / float(seg_w)
            active_cols_mask = col_dark > 0
            mean_col_h = float(col_dark[active_cols_mask].mean()) if active_cols_mask.any() else 0.0

            # Lọc đốm nhiễu/hằn mặt sau rời rạc
            if very_dark < 22 or seg_ink < 55 or (seg_w < 12 and seg_ink < 65):
                continue
            if (float(seg_ink) / float(seg_w)) < 1.3 or fill < 0.045:
                continue
            # Lọc rìa khung ảnh đậm đặc (fill > 0.36) và đường kẻ ngang chân trang / mảnh gãy của nó
            if fill > 0.36:
                continue
            if seg_w >= 80 and zero_ratio < 0.08:
                continue
            if seg_w >= 80 and mean_col_h < 4.6 and zero_ratio < 0.14:
                continue

            sx0 = max(0, s_x - 6)
            sx1 = min(w_img, e_x + 7)
            valid_sub_rects.append([sx0, y0, sx1, y1])

        if not valid_sub_rects:
            continue

        x0_all = valid_sub_rects[0][0]
        x1_all = valid_sub_rects[-1][2]
        line_w = x1_all - x0_all
        # Bỏ dải bóng mép trên/dưới cùng sát rìa cắt ảnh
        if (y0 <= 12 or y1 >= h_img - 10) and (y1 - y0 <= 22 or line_w > 400):
            line_gray = gray[y0:y1, x0_all:x1_all]
            lc = (line_gray < 160).sum(axis=0)
            lz = float((lc == 0).sum()) / float(max(1, line_w))
            lmch = float(lc[lc > 0].mean()) if (lc > 0).any() else 0.0
            if lz < 0.14 or lmch < 5.5 or y1 >= h_img - 10:
                continue

        # Với dòng ngắn đơn lẻ (như 'Phiên âm:', 'Dịch nghĩa:', 'Khâm tai!', 'Kính cẩn thay!'),
        # tìm thung lũng cục bộ trong đúng vùng X [x0_all:x1_all] giữa các peak kề cận (tránh dính chữ dòng dưới)
        if len(valid_sub_rects) == 1 and line_w < 950:
            prev_bound = max(0, pk - max_half_h) if i == 0 else peaks[i - 1]
            next_bound = min(h_img - 1, pk + max_half_h) if i == len(peaks) - 1 else peaks[i + 1]
            span_loc = mask_clean[prev_bound : next_bound + 1, x0_all:x1_all].sum(axis=1).astype(np.float32)
            span_sm = np.convolve(span_loc, np.array([0.2, 0.6, 0.2], dtype=np.float32), mode="same")
            pk_idx = pk - prev_bound
            if i > 0 and pk_idx > 2:
                v_up = prev_bound + int(np.argmin(span_sm[: pk_idx + 1]))
                loc_top = max(v_up, pk - 24)
            else:
                loc_top = max(0, pk - 24)
            if i < len(peaks) - 1 and len(span_sm) - pk_idx > 2:
                v_dn = pk + int(np.argmin(span_sm[pk_idx:]))
                loc_bot = min(v_dn + 1, pk + 26)
            else:
                loc_bot = min(h_img, pk + 26)

            loc_proj = mask_clean[loc_top:loc_bot, x0_all:x1_all].sum(axis=1)
            loc_act = np.where(loc_proj >= 1)[0]
            if len(loc_act) > 0:
                ly0 = max(loc_top, loc_top + int(loc_act[0]) - 2)
                ly1 = min(loc_bot, loc_top + int(loc_act[-1]) + 3)
                if ly1 - ly0 >= 14:
                    y0, y1 = ly0, ly1
                    valid_sub_rects[0][1] = y0
                    valid_sub_rects[0][3] = y1

        pts = np.array([[x0_all, y0], [x1_all, y0], [x1_all, y1], [x0_all, y1]], dtype=np.float32)
        if inv_mat is not None:
            pts_orig = cv2.transform(pts.reshape(1, -1, 2), inv_mat).reshape(-1, 2)
            orig_box = [
                [max(0, min(w_img, int(round(px)))), max(0, min(h_img, int(round(py))))]
                for px, py in pts_orig
            ]
        else:
            orig_box = pts.astype(np.int32).tolist()

        rects.append({
            "x0": x0_all,
            "y0": y0,
            "x1": x1_all,
            "y1": y1,
            "sub_rects": valid_sub_rects,
            "orig_box": orig_box,
        })

    return (rects, work_img) if return_work_img else rects


def split_pa_dn(lines: list[str]) -> tuple[str, str]:
    """
    Tách danh sách các dòng OCR Quốc ngữ thành (phien_am_str, dich_nghia_str)
    đã chuẩn hóa theo Quy ước nội dung.
    """
    phien_am_lines = []
    dich_nghia_lines = []
    current_section = "pa"
    seen_end_pa = False

    pa_header_pat = re.compile(
        r'^(?:phi[êeếềệẻẽ]n\s*[âaă]m\s*[:\d\.\-]*|phi[êeếềệẻẽ]n\s+[^\s:]{1,10}\s*:)',
        re.IGNORECASE,
    )
    dn_header_strict_pat = re.compile(
        r'^(?:[dđbs][iịìỉĩ][cch]?h?\s*\.?\s*ngh?[iĩìỉịeuaăâơớứ]{1,3}[aãeảạitc1l]?)\s*[:\.]?',
        re.IGNORECASE,
    )
    dn_header_noisy_pat = re.compile(
        r'^(?:[dđbls][iịí][cch/0-9\.]{1,4}[\s\.]+[0-9a-zA-ZÀ-ỹ/\.]{2,10})\s*[:\.]?$',
        re.IGNORECASE,
    )
    end_pa_pat = re.compile(r'(kh[âaầẩậ]m\s*t[aạ][iị1l]|c[ốôổồ]\s*s[ắăắằẳặ]c)', re.IGNORECASE)
    date_end_pat = re.compile(
        r'ni[êeềế]n.*nguy[ệêeếề]t.*(?:nh[ậâaă]t|nh[ựư]t).{0,32}$',
        re.IGNORECASE,
    )
    archival_note_pat = re.compile(r'\(\s*l[ễếêẻẽề]\s*[bh]ộ|\(\s*lễ\b|đường\s*cung\s*lục', re.IGNORECASE)
    dn_strong_body_pat = re.compile(
        r'^(?:s[ắá]c\s+ban\s+cho|nay\s+ban\s+s[ắá]c|k[ií]nh\s+c[aẩ]n\s+thay|ng[aà]y\s+\d{1,2}\s+th[aá]ng\b)',
        re.IGNORECASE,
    )

    for raw_line in lines:
        line = clean_text_line(raw_line)
        if not line:
            continue
        l_lower = line.lower().strip()

        # Bỏ qua footnote chú thích chân trang và chú thích sao chép
        if l_lower.startswith("*") or "*nay" in l_lower or "khu phố" in l_lower or "sao chép tại" in l_lower:
            continue
        if archival_note_pat.search(l_lower):
            continue

        # Xử lý tiêu đề Dịch nghĩa trước để không nhầm khi sau dấu ':' có chữ Sắc
        m_dn = dn_header_strict_pat.search(l_lower)
        if m_dn or (len(l_lower) < 28 and dn_header_noisy_pat.search(l_lower)):
            current_section = "dn"
            if ":" in line[:30]:
                after = line.split(":", 1)[1].strip()
                if after:
                    dich_nghia_lines.append(after)
            elif m_dn:
                tail = line[m_dn.end():].strip(" .:-")
                if len(tail) >= 5:
                    dich_nghia_lines.append(tail)
            continue

        # Tiêu đề Phiên âm
        m_pa = pa_header_pat.search(l_lower)
        if m_pa:
            current_section = "pa"
            seen_end_pa = False
            if ":" in line[:25]:
                after = line.split(":", 1)[1].strip()
                if after:
                    phien_am_lines.append(after)
            else:
                tail = line[m_pa.end():].strip(" .:-")
                if len(tail) >= 5:
                    phien_am_lines.append(tail)
            continue

        # Dòng niên hiệu âm lịch (... niên ... nguyệt ... nhật ở cuối dòng) kết thúc phần Phiên âm
        # Tránh nhầm giữa các mục "Phụng sao lịch đại..." (chứa 'sắc phong:' dài phía sau chữ nhật)
        if current_section == "pa" and date_end_pat.search(l_lower) and "sắc phong" not in l_lower:
            phien_am_lines.append(line)
            seen_end_pa = True
            current_section = "dn"
            continue

        # Phát hiện dấu kết thúc 'Khâm tai' hoặc 'Cố sắc'
        if current_section == "pa" and end_pa_pat.search(l_lower):
            phien_am_lines.append(line)
            seen_end_pa = True
            continue

        # Ngay sau 'Khâm tai' / 'Cố sắc': thu nốt dòng ngày âm lịch (nếu có) rồi chuyển sang Dịch nghĩa
        if seen_end_pa and current_section == "pa":
            if dn_strong_body_pat.search(l_lower):
                current_section = "dn"
            elif (
                re.search(r'\bnh[ậâaă]t\b|\bni[êe]n\b|\bnguy[ệêe]t\b', l_lower)
                and "năm" not in l_lower
                and "ngày" not in l_lower
                and "sắc ban" not in l_lower
            ):
                phien_am_lines.append(line)
                if re.search(r'nh[ậâaă]t', l_lower):
                    current_section = "dn"
                continue
            else:
                current_section = "dn"

        # Fallback: gặp cụm mở đầu đặc trưng của bản Dịch nghĩa
        if current_section == "pa" and dn_strong_body_pat.search(l_lower):
            current_section = "dn"

        # Loại bỏ dòng tiêu đề Dịch nghĩa bị OCR hỏng quá nặng thành ký tự rác (< 18 ký tự)
        if (
            current_section == "dn"
            and len(dich_nghia_lines) == 0
            and len(line) < 18
            and not re.search(r'(?:sắc|thần|nay|kính|ngày|trong|ban)', l_lower)
        ):
            continue

        if current_section == "pa":
            phien_am_lines.append(line)
        elif current_section == "dn":
            dich_nghia_lines.append(line)

    pa_str = clean_and_correct_sac_phong_viet(" ".join(phien_am_lines), is_dich_nghia=False)
    dn_str = clean_and_correct_sac_phong_viet(" ".join(dich_nghia_lines), is_dich_nghia=True)
    return pa_str, dn_str

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
    full_img = _imread_bgr(viet_img_path)
    if full_img is None:
        return "", "", "", []

    h_img, w_img = full_img.shape[:2]

    # Layout A khổ rộng (> 1800px): dùng Peak-Valley Projection chống gộp dòng DBNet
    rects = []
    used_projection = False
    work_img = full_img
    if w_img > 1800:
        rects, work_img = _segment_viet_lines_projection(full_img, return_work_img=True)
        used_projection = bool(rects)

    if not rects:
        work_img = full_img
        det_engine = get_viet_detector()
        res, _ = det_engine(full_img)
        if not res:
            return "", "", "", []

        sorted_res = sorted(res, key=lambda b: min(pt[1] for pt in b[0]))
        for box, _, _ in sorted_res:
            pts = np.array(box, dtype=np.int32)
            x, y, w, h = cv2.boundingRect(pts)
            rects.append({
                "x0": max(0, x - 2),
                "y0": max(0, y - 2),
                "x1": min(w_img, x + w + 2),
                "y1": min(h_img, y + h + 2),
                "orig_box": box,
            })

        # Khử overlap chiều dọc trên box DBNet
        for idx in range(len(rects) - 1):
            r_curr = rects[idx]
            r_next = rects[idx + 1]
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

        if used_projection and r.get("sub_rects") and len(r["sub_rects"]) > 1:
            sub_parts = []
            for sx0, sy0, sx1, sy1 in r["sub_rects"]:
                sub_crop = work_img[sy0:sy1, sx0:sx1]
                sub_txt = clean_text_line(recognize_viet_line(sub_crop))
                if sub_txt:
                    sub_parts.append(sub_txt)
            line_txt = clean_text_line(" ".join(sub_parts))
        else:
            crop = work_img[y0:y1, x0:x1]
            line_txt = clean_text_line(recognize_viet_line(crop))

        if not line_txt:
            continue

        lines.append(line_txt)
        int_box = [[int(pt[0]), int(pt[1])] for pt in r["orig_box"]]
        boxes_data.append({
            "transcription": line_txt,
            "points": int_box,
        })

    full_text = "\n".join(lines)
    pa_str, dn_str = split_pa_dn(lines)
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
    img = _imread_bgr(han_img_path)
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
        for box, text, score in res_direct:
            txt = clean_text_line(text)
            if not txt: continue
            int_box = [[int(pt[0]), int(pt[1])] for pt in box]
            boxes_data.append({"transcription": txt, "points": int_box, "score": round(float(score), 4)})
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
            "x_center": x_center,
            "score": round(float(score), 4),
        })

    # Sắp xếp các cột từ PHẢI SANG TRÁI (x_center giảm dần)
    cols.sort(key=lambda c: -c["x_center"])

    lines = [c["text"] for c in cols]
    # "score" (độ tin cậy nhận dạng) dùng để lọc dòng rác; bỏ khi ghi Label.txt (PPOCRLabel chỉ cần 2 khóa)
    boxes_data = [{"transcription": c["text"], "points": c["box"], "score": c["score"]} for c in cols]
    
    han_text = "\n".join(lines)
    return han_text, boxes_data
