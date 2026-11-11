"""
layout_parser.py — Phân tích bố cục trang bằng pixel-brightness analysis.

Phát hiện và cắt chính xác 2 layout trang sách sắc phong:
  - Layout A: 1 sắc phong / trang — ảnh Hán lớn ở TRÊN (~60% chiều cao),
              Phiên âm + Dịch nghĩa ở DƯỚI (toàn chiều rộng).
  - Layout B: 2 sắc phong / trang — 2 ảnh Hán xếp dọc ở BÊN TRÁI (~60% chiều rộng),
              2 khối Phiên âm + Dịch nghĩa ở BÊN PHẢI.

Thuật toán: So sánh brightness trung bình vùng trái/phải để phân loại layout,
sau đó dùng gradient brightness để tìm điểm cắt chính xác.
"""
import numpy as np
from pathlib import Path
from PIL import Image


# ─────────────────────────── Hằng số margin ───────────────────────────────
# Tỉ lệ cắt biên để bỏ header tiêu đề và footer số trang
_MARGIN_TOP_RATIO = 0.075   # bỏ 7.5% trên (header "SẮC PHONG LƯU TẠI…")
_MARGIN_BOT_RATIO = 0.955   # giữ đến 95.5% chiều cao (bỏ footer số trang)
_MARGIN_L_RATIO   = 0.020   # bỏ 2% trái
_MARGIN_R_RATIO   = 0.985   # giữ đến 98.5% chiều rộng (vùng Hán)
_MARGIN_VIET_R_RATIO = 0.998  # giữ sát mép phải 99.8% cho vùng Quốc ngữ để không cắt mất chữ cuối dòng


def _margins(h: int, w: int):
    """Trả về (mt, mb, ml, mr) pixel từ tỉ lệ margin."""
    return (
        int(h * _MARGIN_TOP_RATIO),
        int(h * _MARGIN_BOT_RATIO),
        int(w * _MARGIN_L_RATIO),
        int(w * _MARGIN_R_RATIO),
    )


# ─────────────────────────── Phát hiện Layout ─────────────────────────────

def detect_layout(img_path: str) -> str:
    """
    Phát hiện Layout A hay Layout B dựa trên đặc trưng hình học & màu sắc của trang in:
    - Layout B: 2 ảnh bên trái, cột text Quốc ngữ bên phải. Nửa trên bên phải (x: 72%-88%, y: 20%-45%)
      là NỀN GIẤY TRẮNG IN CHỮ (R ≈ G ≈ B, color_diff rất nhỏ < 15, độ sáng rất cao > 210, white_ratio > 0.35).
    - Layout A: 1 ảnh to ở trên, text ở dưới. Nửa trên bên phải là BỀ MẶT SẮC PHONG (màu vàng/đỏ/cam
      hoặc vải lụa có vân hoa, color_diff > 15, không phải giấy in sách trắng).
    """
    img = Image.open(img_path).convert('RGB')
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]

    # Vùng kiểm tra: góc trên bên phải (nơi chứa cột text nếu là Layout B, hoặc chứa thân sắc phong nếu là Layout A)
    top_right = arr[int(h * 0.20):int(h * 0.45), int(w * 0.72):int(w * 0.88)]
    
    # Tỉ lệ pixel trắng tinh của giấy in
    white_ratio = (top_right.mean(axis=2) > 230).mean()
    
    # Độ chênh lệch màu: giấy in trắng/xám có R ≈ G ≈ B nên color_diff < 15.
    # Trong khi sắc phong có màu vàng/cam/đỏ nên color_diff > 20.
    color_diff = (
        np.abs(top_right[:, :, 0] - top_right[:, :, 1]) +
        np.abs(top_right[:, :, 1] - top_right[:, :, 2])
    ).mean()
    
    mean_val = top_right.mean()
    
    is_layout_b = (color_diff < 15.0) and (white_ratio > 0.35 or mean_val > 210.0)
    return 'B' if is_layout_b else 'A'


# ─────────────────────── Tìm điểm cắt Layout A ────────────────────────────

def _find_split_y_layout_a(arr: np.ndarray, h: int, w: int) -> int:
    """
    Tìm ranh giới Y phân chia ảnh sắc phong (trên) và text (dưới) — Layout A.

    Phương pháp: Scan brightness trung bình từng hàng pixel theo chiều ngang
    (dải giữa 10%–90% chiều rộng để tránh nhiễu lề), làm mượt bằng moving average,
    rồi tìm vị trí có JUMP (tăng đột biến) lớn nhất trong dải 35%–75% chiều cao
    — đó là ranh giới chuyển từ ảnh tối → nền trắng của text.
    """
    mid_strip = arr[:, int(w * 0.1):int(w * 0.9)]
    row_br = np.array([mid_strip[r, :].mean() for r in range(h)], dtype=np.float32)

    kernel_size = 50
    smoothed = np.convolve(row_br, np.ones(kernel_size) / kernel_size, mode='same')

    search_start = int(h * 0.35)
    search_end   = int(h * 0.75)
    max_jump = 0
    split_y  = int(h * 0.60)  # fallback

    for r in range(search_start, search_end - 20):
        jump = smoothed[r + 20] - smoothed[r]
        if jump > max_jump:
            max_jump = jump
            split_y = r + 10  # dịch về phía sau điểm jump

    return split_y


# ─────────────────────── Tìm điểm cắt Layout B ────────────────────────────

def _find_split_layout_b(arr: np.ndarray, h: int, w: int):
    """
    Tìm split_x (ảnh Hán | text Việt) và split_y (tờ 1 | tờ 2) — Layout B.

    split_x: Scan brightness trung bình từng CỘT trong vùng core (10%–90% chiều cao).
    Làm mượt, sau đó tìm vị trí DROP (giảm đột biến) lớn nhất khi quét từ PHẢI sang TRÁI
    trong dải 40%–70% chiều rộng. Nơi drop mạnh nhất = biên ảnh / text.

    split_y: Scan brightness trung bình từng HÀNG trong nửa trái (vùng ảnh).
    Vị trí sáng nhất trong dải 35%–65% chiều cao = khoảng trắng giữa 2 tờ sắc phong.
    """
    kernel_size = 100
    kernel = np.ones(kernel_size) / kernel_size

    # --- Tìm split_x ---
    core = arr[int(h * 0.1):int(h * 0.9), :]
    col_br = np.array([core[:, c].mean() for c in range(w)], dtype=np.float32)
    smoothed_x = np.convolve(col_br, kernel, mode='same')

    search_x_start = int(w * 0.40)
    search_x_end   = int(w * 0.70)
    max_drop = 0
    split_x  = int(w * 0.58)  # fallback

    for c in range(search_x_end, search_x_start, -1):
        drop = smoothed_x[c] - smoothed_x[c - 50]
        if drop > max_drop:
            max_drop = drop
            split_x = c - 25

    # --- Tìm split_y ---
    left_strip = arr[:, int(w * 0.05):int(split_x * 0.9)]
    row_br = np.array([left_strip[r, :].mean() for r in range(h)], dtype=np.float32)
    smoothed_y = np.convolve(row_br, kernel, mode='same')

    search_y_start = int(h * 0.35)
    search_y_end   = int(h * 0.65)
    max_br = 0
    split_y = int(h * 0.50)  # fallback

    for r in range(search_y_start, search_y_end):
        if smoothed_y[r] > max_br:
            max_br = smoothed_y[r]
            split_y = r

    return split_x, split_y


# ─────────────────────── Hàm chính: crop trang ────────────────────────────

def process_and_crop_page(
    img_path: str,
    page_num: int,
    output_base_dir: str,
    ma_sach: str,
    doc_counter: int
) -> list:
    """
    Phân tích bố cục trang, cắt ảnh Hán và ảnh Việt, lưu vào thư mục đầu ra.

    Args:
        img_path:         Đường dẫn tới ảnh trang (JPEG đã extract từ PDF).
        page_num:         Số trang trong PDF (1-indexed).
        output_base_dir:  Thư mục gốc đầu ra (ví dụ: "S113PH/").
        ma_sach:          Mã sách (ví dụ: "S113PH").
        doc_counter:      Số thứ tự văn bản bắt đầu từ trang này (tăng dần).

    Returns:
        Danh sách dict, mỗi dict mô tả 1 văn bản đã cắt:
        [{'doc_id': str, 'page_num': int, 'layout': str,
          'han_img': str, 'viet_img': str, 'header': str}]
    """
    img_path = Path(img_path)
    out_han_dir  = Path(output_base_dir) / "02_ocr_tho" / "han"
    out_viet_dir = Path(output_base_dir) / "02_ocr_tho" / "viet"
    out_han_dir.mkdir(parents=True, exist_ok=True)
    out_viet_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(str(img_path)).convert('RGB')
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]

    mt, mb, ml, mr = _margins(h, w)
    mr_viet = int(w * _MARGIN_VIET_R_RATIO)

    layout = detect_layout(str(img_path))
    docs   = []

    # ── Layout A: 1 sắc phong ──
    if layout == 'A':
        doc_id = f"{ma_sach}.{doc_counter:03d}"
        sy = _find_split_y_layout_a(arr, h, w)

        han_file  = out_han_dir  / f"{doc_id}_1.jpg"
        viet_file = out_viet_dir / f"{doc_id}_1.jpg"

        img.crop((ml, mt, mr, sy)).save(han_file,  quality=95)
        img.crop((ml, sy, mr_viet, mb)).save(viet_file, quality=95)

        docs.append({
            "doc_id":   doc_id,
            "page_num": page_num,
            "layout":   "A",
            "header":   "",
            "han_img":  str(han_file),
            "viet_img": str(viet_file),
        })
        print(f"[+] Trang {page_num} (Layout A): {doc_id}  |  split_y={sy} ({sy/h*100:.1f}%)")

    # ── Layout B: 2 sắc phong ──
    else:
        sx, sy = _find_split_layout_b(arr, h, w)

        doc1_id = f"{ma_sach}.{doc_counter:03d}"
        doc2_id = f"{ma_sach}.{(doc_counter + 1):03d}"

        han1_file  = out_han_dir  / f"{doc1_id}_1.jpg"
        viet1_file = out_viet_dir / f"{doc1_id}_1.jpg"
        han2_file  = out_han_dir  / f"{doc2_id}_1.jpg"
        viet2_file = out_viet_dir / f"{doc2_id}_1.jpg"

        # Tờ 1: trái trên / phải trên
        img.crop((ml, mt, sx, sy)).save(han1_file,  quality=95)
        img.crop((sx, mt, mr_viet, sy)).save(viet1_file, quality=95)
        # Tờ 2: trái dưới / phải dưới
        img.crop((ml, sy, sx, mb)).save(han2_file,  quality=95)
        img.crop((sx, sy, mr_viet, mb)).save(viet2_file, quality=95)

        docs.append({
            "doc_id":   doc1_id,
            "page_num": page_num,
            "layout":   "B_top",
            "header":   "",
            "han_img":  str(han1_file),
            "viet_img": str(viet1_file),
        })
        docs.append({
            "doc_id":   doc2_id,
            "page_num": page_num,
            "layout":   "B_bottom",
            "header":   "",
            "han_img":  str(han2_file),
            "viet_img": str(viet2_file),
        })
        print(
            f"[+] Trang {page_num} (Layout B): {doc1_id} & {doc2_id}"
            f"  |  split_x={sx} ({sx/w*100:.1f}%), split_y={sy} ({sy/h*100:.1f}%)"
        )

    return docs


# ─────────────────────── Quick test ───────────────────────────────────────
if __name__ == "__main__":
    import os
    os.makedirs("test_layout_output/02_ocr_tho/han",  exist_ok=True)
    os.makedirs("test_layout_output/02_ocr_tho/viet", exist_ok=True)

    test_pages = [
        ("cache_pages/S113PH/page_004.jpg", 4),
        ("cache_pages/S113PH/page_005.jpg", 5),
        ("cache_pages/S113PH/page_006.jpg", 6),
        ("cache_pages/S113PH/page_007.jpg", 7),
        ("cache_pages/S113PH/page_008.jpg", 8),
    ]
    counter = 1
    for path, pnum in test_pages:
        docs = process_and_crop_page(path, pnum, "test_layout_output", "S113PH", counter)
        counter += len(docs)

    print("\n[OK] Quick test hoàn tất. Kiểm tra thư mục test_layout_output/")
