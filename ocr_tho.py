"""
ocr_tho.py — Pipeline trích xuất PDF và tạo dữ liệu OCR thô (02_ocr_tho) Sắc phong (R1001 / R1003).

Cách dùng:
    # 1. Chạy thử nghiệm trên 4 trang mẫu (trang 4 đến 7 của tập 1):
    python ocr_tho.py --pdf "tap 1.pdf" --pages 4-7 --ma-sach R1001

    # 2. Chạy trọn vẹn tập 1 (tất cả các trang sắc phong từ trang 4 đến 178):
    python ocr_tho.py --pdf "tap 1.pdf" --pages 4-178 --ma-sach R1001

    # 3. Chạy tập 3 (trang 5 đến 252):
    python ocr_tho.py --pdf "tap 3.pdf" --pages 5-252 --ma-sach R1003

Đầu ra được tạo đúng theo quy định hợp đồng nộp bài:
<MA_SACH>/
  ├── 01_nguon/
  │   └── <ten_file>.pdf
  ├── 02_ocr_tho/
  │   ├── han/
  │   │   ├── <doc_id>_1.jpg
  │   │   ├── <doc_id>.txt
  │   │   ├── Label.txt
  │   │   └── fileState.txt
  │   └── viet/
  │       ├── <doc_id>_1.jpg
  │       ├── <doc_id>.txt
  │       ├── Label.txt
  │       └── fileState.txt
  ├── 03_text_sach/
  │   ├── han.txt
  │   ├── phien_am.txt
  │   └── dich_nghia.txt
  └── page_mapping.tsv
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Đảm bảo UTF-8 cho console stdout/stderr trên Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Đảm bảo import được các module trong src/ và han_viet_alignment
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

try:
    from han_viet_alignment.sac_phong import (
        extract_page_images,
        process_and_crop_page,
        process_viet_ocr,
        process_han_ocr,
        get_corrector,
        syl_key
    )
except ImportError:
    from src.pdf_extractor import extract_page_images
    from src.layout_parser import process_and_crop_page
    from src.ocr_pipeline import process_viet_ocr, process_han_ocr
    from src.han_auto_corrector import get_corrector, syl_key

def parse_page_range(pages_str: str, max_pages: int):
    """Phân tích chuỗi trang, ví dụ: '4-7' hoặc '5' hoặc 'all'."""
    if not pages_str or pages_str.lower() == "all":
        return 1, max_pages
    if "-" in pages_str:
        parts = pages_str.split("-")
        start = int(parts[0].strip())
        end = int(parts[1].strip())
        return start, min(end, max_pages)
    else:
        p = int(pages_str.strip())
        return p, p

def main():
    parser = argparse.ArgumentParser(description="Pipeline trích xuất PDF & tạo dữ liệu OCR thô (02_ocr_tho) Sắc phong R1001 / R1003")
    parser.add_argument("--pdf", default="tap 1.pdf", help="Đường dẫn file PDF sách (mặc định: 'tap 1.pdf')")
    parser.add_argument("--pages", default="4-178", help="Dải trang cần chạy, ví dụ '4-7' hoặc '4-178' (mặc định: '4-178')")
    parser.add_argument("--ma-sach", default=None, help="Mã sách quy định (mặc định: 'R1001' cho tập 1, 'R1003' cho tập 3)")
    parser.add_argument("--out-dir", default=None, help="Thư mục xuất kết quả (mặc định: ./<ma-sach>)")
    parser.add_argument("--cache-dir", default="cache_pages", help="Thư mục tạm lưu ảnh trang PDF")
    parser.add_argument("--force", action="store_true", default=False, help="Chạy lại từ đầu, ghi đè toàn bộ các văn bản cũ")
    
    args = parser.parse_args()
    
    # Tự động nhận diện mã sách chuẩn theo phân công đồ án: R1001 (Tập 1), R1003 (Tập 3)
    if args.ma_sach:
        ma_sach = args.ma_sach
    else:
        ma_sach = "R1003" if "3" in str(args.pdf) else "R1001"
    out_dir = Path(args.out_dir if args.out_dir else ma_sach)
    cache_dir = Path(args.cache_dir) / ma_sach
    
    # 1. Xác định số trang của file PDF
    import pypdf
    reader = pypdf.PdfReader(args.pdf)
    total_pages = len(reader.pages)
    start_p, end_p = parse_page_range(args.pages, total_pages)
    
    print("=" * 70)
    print(f"🚀 PIPELINE TRÍCH XUẤT PDF & OCR (SẮC PHONG)")
    print(f"  • File nguồn: {args.pdf} (tổng cộng {total_pages} trang)")
    print(f"  • Phạm vi trang xử lý: trang {start_p} đến {end_p}")
    print(f"  • Mã sách: {ma_sach}")
    print(f"  • Thư mục đích: {out_dir}")
    print("=" * 70)
    
    # 0. Tạo thư mục 01_nguon và lưu file PDF gốc theo đúng quy cách đồ án
    nguon_dir = out_dir / "01_nguon"
    nguon_dir.mkdir(parents=True, exist_ok=True)
    dst_pdf = nguon_dir / Path(args.pdf).name
    if not dst_pdf.exists() and Path(args.pdf).exists():
        import shutil
        shutil.copy2(args.pdf, dst_pdf)
        print(f"[✓] Đã sao lưu PDF gốc vào {dst_pdf}")

    # 1. Trích xuất ảnh trang PDF chất lượng gốc
    print("\n[BƯỚC 1/4] Trích xuất ảnh PDF sang bộ nhớ đệm...")
    page_records = extract_page_images(args.pdf, str(cache_dir), start_p, end_p)
    
    # 3. Bước 2: Phân tích bố cục và cắt ảnh sắc phong
    print("\n[BƯỚC 2/4] Phân tích bố cục và cắt ảnh sắc phong (<doc_id>_1.jpg)...")
    all_docs = []
    
    # Tự động tiếp nối số thứ tự văn bản nếu đã có sẵn trong thư mục
    existing_docs = list((out_dir / "02_ocr_tho" / "han").glob(f"{ma_sach}.*_1.jpg")) if (out_dir / "02_ocr_tho" / "han").exists() else []
    if existing_docs and start_p > 4:
        # Tìm số lớn nhất hiện có
        nums = []
        for f in existing_docs:
            m = re.search(rf"{re.escape(ma_sach)}\.(\d+)_1\.jpg", f.name)
            if m:
                nums.append(int(m.group(1)))
        doc_counter = max(nums) + 1 if nums else 1
        print(f"[*] Phát hiện {len(existing_docs)} văn bản cũ, tiếp tục đánh số từ {ma_sach}.{doc_counter:03d}")
    else:
        doc_counter = 1
    
    for prec in page_records:
        page_img = prec["image_path"]
        page_num = prec["page_num"]
        docs = process_and_crop_page(page_img, page_num, str(out_dir), ma_sach, doc_counter)
        if docs:
            all_docs.extend(docs)
            doc_counter += len(docs)
            
    print(f"[✓] Đã tìm thấy và cắt ảnh cho {len(all_docs)} văn bản sắc phong.")
    
    # 4. Bước 3: Chạy OCR cho các vùng và sinh Label.txt
    print("\n[BƯỚC 3/4] Chạy OCR cho chữ Hán, Phiên âm và Dịch nghĩa...")
    corrector = get_corrector()
    
    han_label_lines = []
    viet_label_lines = []
    han_filestate_lines = []
    viet_filestate_lines = []
    
    text_sach_han = []
    text_sach_pa = []
    text_sach_dn = []
    
    out_han_dir = out_dir / "02_ocr_tho" / "han"
    out_viet_dir = out_dir / "02_ocr_tho" / "viet"
    out_text_dir = out_dir / "03_text_sach"
    out_text_dir.mkdir(parents=True, exist_ok=True)
    
    for i, doc in enumerate(all_docs):
        doc_id = doc["doc_id"]
        meta_file = out_viet_dir / f"{doc_id}_meta.json"
        han_file = out_han_dir / f"{doc_id}.txt"
        viet_file = out_viet_dir / f"{doc_id}.txt"
        
        viet_img_rel = f"viet/{doc_id}_1.jpg"
        han_img_rel = f"han/{doc_id}_1.jpg"

        if not args.force and meta_file.exists() and han_file.exists() and viet_file.exists():
            print(f"  -> [{i+1}/{len(all_docs)}] Đã có sẵn dữ liệu OCR cho {doc_id} (Trang {doc['page_num']}) -> Tái sử dụng.")
            try:
                mdata = json.loads(meta_file.read_text(encoding="utf-8"))
                corr_han_txt = han_file.read_text(encoding="utf-8")
                pa_txt = mdata.get("pa", "")
                dn_txt = mdata.get("dn", "")
                vi_boxes = mdata.get("vi_boxes", [])
                han_boxes = mdata.get("han_boxes", [])
            except Exception:
                # Nếu file lỗi thì chạy lại OCR
                corr_han_txt = None
        else:
            corr_han_txt = None

        if corr_han_txt is None:
            print(f"  -> [{i+1}/{len(all_docs)}] Đang OCR văn bản {doc_id} (Trang {doc['page_num']})...")
            # OCR Tiếng Việt (Phiên âm + Dịch nghĩa)
            full_vi_txt, pa_txt, dn_txt, vi_boxes = process_viet_ocr(doc["viet_img"], doc_id)
            
            # Lưu file thô tiếng Việt (giữ nguyên số trang và footnote)
            viet_file.write_text(full_vi_txt, encoding="utf-8")
            
            # OCR Chữ Hán
            han_txt, han_boxes = process_han_ocr(doc["han_img"], doc_id)
            
            # Tự động sửa lỗi chữ Hán (Auto-Correction) kết hợp Phiên âm và Từ điển Hán Nôm
            corr_han_txt, details = corrector.correct_han(han_txt, pa_txt)
            n_ok = sum(1 for d in details if syl_key(d['syllable']) in corrector.han_readings.get(d['char'], ()))
            acc = (n_ok / len(details) * 100) if details else 0
            print(f"      [Auto-Correction] Chữ Hán khớp âm từ điển: {n_ok}/{len(details)} ({acc:.1f}%)")
            
            # Lưu file chữ Hán đã sửa chuẩn xác vào 02_ocr_tho/han/<doc_id>.txt
            han_file.write_text(corr_han_txt, encoding="utf-8")
            
            # Lưu meta cache để resume
            meta_file.write_text(json.dumps({
                "pa": pa_txt,
                "dn": dn_txt,
                "vi_boxes": vi_boxes,
                "han_boxes": han_boxes
            }, ensure_ascii=False), encoding="utf-8")
        
        # Ghi Label.txt theo format: <folder>/<image>\t<json_boxes>
        viet_label_lines.append(f"{viet_img_rel}\t{json.dumps(vi_boxes, ensure_ascii=False)}")
        viet_filestate_lines.append(f"{viet_img_rel}\t1")
        han_label_lines.append(f"{han_img_rel}\t{json.dumps(han_boxes, ensure_ascii=False)}")
        han_filestate_lines.append(f"{han_img_rel}\t1")
        
        # Tích lũy cho 03_text_sach/ (Chữ Hán chuẩn hóa phục vụ dóng hàng)
        text_sach_han.append(f"### {doc_id}\n{corr_han_txt}\n")
        text_sach_pa.append(f"### {doc_id}\n{pa_txt}\n")
        dn_final = dn_txt if dn_txt.strip() else "[Sách gốc không có bản dịch]"
        text_sach_dn.append(f"### {doc_id}\n{dn_final}\n")
        
        # Ghi file định kỳ sau mỗi 10 văn bản hoặc văn bản cuối cùng để chống mất dữ liệu
        if (i + 1) % 10 == 0 or (i + 1) == len(all_docs):
            (out_viet_dir / "Label.txt").write_text("\n".join(viet_label_lines) + "\n", encoding="utf-8")
            (out_viet_dir / "fileState.txt").write_text("\n".join(viet_filestate_lines) + "\n", encoding="utf-8")
            (out_han_dir / "Label.txt").write_text("\n".join(han_label_lines) + "\n", encoding="utf-8")
            (out_han_dir / "fileState.txt").write_text("\n".join(han_filestate_lines) + "\n", encoding="utf-8")
            (out_text_dir / "han.txt").write_text("\n".join(text_sach_han) + "\n", encoding="utf-8")
            (out_text_dir / "phien_am.txt").write_text("\n".join(text_sach_pa) + "\n", encoding="utf-8")
            (out_text_dir / "dich_nghia.txt").write_text("\n".join(text_sach_dn) + "\n", encoding="utf-8")
        
    # Ghi file Label.txt, fileState.txt và 03_text_sach (tự động append nếu chạy theo từng cụm trang)
    def append_or_write(filepath, new_lines):
        if filepath.exists() and start_p > 4:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
        else:
            filepath.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    append_or_write(out_viet_dir / "Label.txt", viet_label_lines)
    append_or_write(out_viet_dir / "fileState.txt", viet_filestate_lines)
    append_or_write(out_han_dir / "Label.txt", han_label_lines)
    append_or_write(out_han_dir / "fileState.txt", han_filestate_lines)
    
    # 5. Bước 4: Xuất các file 03_text_sach bàn giao cho Người 2 (anh Kiên)
    print("\n[BƯỚC 4/4] Xuất các file 03_text_sach/ bàn giao cho Người 2...")
    append_or_write(out_text_dir / "han.txt", text_sach_han)
    append_or_write(out_text_dir / "phien_am.txt", text_sach_pa)
    append_or_write(out_text_dir / "dich_nghia.txt", text_sach_dn)
    
    # Báo cáo tóm tắt & Bảng ánh xạ số trang bàn giao cho Người 2
    summary = {
        "ma_sach": ma_sach,
        "source_pdf": str(args.pdf),
        "pages_processed": f"{start_p} -> {end_p}",
        "total_docs": len(all_docs),
        "docs": [{"doc_id": d["doc_id"], "page": d["page_num"], "header": d["header"]} for d in all_docs]
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # Xuất file page_mapping.tsv để Người 2 tra cứu số trang trực tiếp
    page_map_lines = ["doc_id\tpdf_page\tbook_page\tlayout_type\than_image\tviet_image"]
    for d in all_docs:
        book_p = d['page_num'] + 1  # Trang sách in = Trang PDF + 1 (do 3 trang đầu là bìa và lời tựa)
        page_map_lines.append(f"{d['doc_id']}\t{d['page_num']}\t{book_p}\t{d.get('layout', 'unknown')}\than/{d['doc_id']}_1.jpg\tviet/{d['doc_id']}_1.jpg")
    (out_dir / "page_mapping.tsv").write_text("\n".join(page_map_lines) + "\n", encoding="utf-8")
    
    print("\n" + "=" * 70)
    print(f"🎉 HOÀN THÀNH XUẤT SẮC!")
    print(f"  • Tổng số văn bản đã trích xuất: {len(all_docs)}")
    print(f"  • Thư mục nộp bài chuẩn quy định: {out_dir.resolve()}")
    print(f"  • File bàn giao cho Người 2 (anh Kiên):")
    print(f"      - {out_text_dir / 'han.txt'}")
    print(f"      - {out_text_dir / 'phien_am.txt'}")
    print(f"      - {out_text_dir / 'dich_nghia.txt'}")
    print("=" * 70)

if __name__ == "__main__":
    main()

