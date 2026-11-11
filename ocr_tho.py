"""
ocr_tho.py — Pipeline trích xuất PDF và tạo dữ liệu OCR thô (02_ocr_tho) Sắc phong (R1001 / R1003).

Cách dùng (đặt PDF vào docs-local/NLP-20261101T150232Z-1-001/NLP/, chỉ cần truyền tên file):
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
import re
import sys
from pathlib import Path

# Thư mục lưu trữ PDF sách gốc (local, không commit — xem .gitignore và metadata/books.json)
SOURCE_DIR = Path(__file__).parent / "docs-local" / "NLP-20261101T150232Z-1-001" / "NLP"


def resolve_pdf(pdf_arg: str) -> Path:
    """Tìm PDF: dùng đường dẫn đã cho nếu tồn tại, ngược lại tìm theo tên trong SOURCE_DIR."""
    p = Path(pdf_arg)
    if p.exists():
        return p
    candidate = SOURCE_DIR / p.name
    if candidate.exists():
        return candidate
    sys.exit(f"[!] Không tìm thấy PDF '{pdf_arg}'. Hãy đặt file vào: {SOURCE_DIR}")

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
        syl_key,
        format_han_content,
        format_phien_am_content,
        format_dich_nghia_content
    )
except ImportError:
    from src.han_viet_alignment.sac_phong import (
        extract_page_images,
        process_and_crop_page,
        process_viet_ocr,
        process_han_ocr,
        get_corrector,
        syl_key,
        format_han_content,
        format_phien_am_content,
        format_dich_nghia_content
    )

from han_viet_alignment.alignment.han_filter import filter_han_lines  # noqa: E402
from han_viet_alignment.common.dictionary import load_readings  # noqa: E402

DROP_LOG_COLUMNS = ["doc_id", "score", "khop_am", "so_chu", "dong_bi_loai"]


def build_han_clean(corrector, han_raw: str, han_boxes: list, pa_txt: str, doc_id: str, drop_log: list):
    """OCR thô -> lọc dòng rác (điểm thấp + không khớp âm) -> sửa chữ giống hình -> chuỗi Hán cho 03_text_sach.

    02_ocr_tho/han/<doc_id>.txt không bị ảnh hưởng (vẫn là OCR thô đầy đủ).
    """
    lines = han_raw.split("\n")
    scores = [b.get("score") for b in han_boxes] if len(han_boxes) == len(lines) else [None] * len(lines)
    infos = filter_han_lines(lines, scores, pa_txt, load_readings())
    for info in infos:
        if not info.kept:
            drop_log.append({"doc_id": doc_id, "score": f"{info.score:.2f}", "khop_am": f"{info.n_match}/{info.n_han}",
                             "so_chu": str(info.n_han), "dong_bi_loai": info.text})
    kept = "\n".join(info.text for info in infos if info.kept)
    corrected, details = corrector.correct_han(kept, pa_txt)
    return corrected, details


def write_drop_log(ma_sach: str, drop_log: list, doc_ids: set) -> None:
    """workspace/<MA_SACH>/han_dong_bi_loai.tsv: thay mục của các văn bản vừa chạy, giữ mục của đợt trước."""
    path = Path(__file__).parent / "workspace" / ma_sach / "han_dong_bi_loai.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if path.exists():
        old = path.read_text(encoding="utf-8").splitlines()[1:]
        rows = [r.split("\t") for r in old if r and r.split("\t")[0] not in doc_ids]
    rows += [[r[c] for c in DROP_LOG_COLUMNS] for r in drop_log]
    rows.sort(key=lambda r: r[0])
    text = "\n".join(["\t".join(DROP_LOG_COLUMNS)] + ["\t".join(r) for r in rows]) + "\n"
    path.write_bytes(text.encode("utf-8"))
    print(f"[*] Đã loại {len(drop_log)} dòng OCR chữ Hán rác (điểm < 0.5 và khớp âm < 30%) -> {path}")


def label_boxes(boxes: list) -> list:
    """Label.txt theo PPOCRLabel: chỉ transcription + points."""
    return [{"transcription": b["transcription"], "points": b["points"]} for b in boxes]


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
    parser.add_argument("--pdf", default="tap 1.pdf", help="Tên hoặc đường dẫn file PDF; tên trần sẽ được tìm trong docs-local/NLP-20261101T150232Z-1-001/NLP/ (mặc định: 'tap 1.pdf')")
    parser.add_argument("--pages", default="4-178", help="Dải trang cần chạy, ví dụ '4-7' hoặc '4-178' (mặc định: '4-178')")
    parser.add_argument("--ma-sach", default=None, help="Mã sách quy định (mặc định: 'R1001' cho tập 1, 'R1003' cho tập 3)")
    parser.add_argument("--out-dir", default=None, help="Thư mục xuất kết quả (mặc định: ./<ma-sach>)")
    parser.add_argument("--cache-dir", default="cache_pages", help="Thư mục tạm lưu ảnh trang PDF")
    parser.add_argument("--force", action="store_true", default=False, help="Chạy lại từ đầu, ghi đè toàn bộ các văn bản cũ")
    parser.add_argument("--update-text-only", action="store_true", default=False, help="Chỉ chuẩn hóa lại 03_text_sach theo đúng Quy ước nội dung từ dữ liệu OCR hiện có")
    
    args = parser.parse_args()
    
    # Tự động nhận diện mã sách chuẩn theo phân công đồ án: R1001 (Tập 1), R1003 (Tập 3)
    if args.ma_sach:
        ma_sach = args.ma_sach
    else:
        ma_sach = "R1003" if "3" in Path(args.pdf).name else "R1001"
    out_dir = Path(args.out_dir if args.out_dir else ma_sach)
    cache_dir = Path(args.cache_dir) / ma_sach
    
    # Chế độ chuẩn hóa nhanh toàn bộ 03_text_sach từ cache theo Quy ước nội dung
    if args.update_text_only:
        print("=" * 70)
        print(f"🚀 CHUẨN HÓA 03_TEXT_SACH THEO QUY ƯỚC NỘI DUNG ({ma_sach})")
        print("=" * 70)
        out_viet_dir = out_dir / "02_ocr_tho" / "viet"
        out_han_dir = out_dir / "02_ocr_tho" / "han"
        out_text_dir = out_dir / "03_text_sach"
        out_text_dir.mkdir(parents=True, exist_ok=True)
        
        meta_dir = cache_dir / "meta"
        meta_files = sorted(meta_dir.glob("*_meta.json"), key=lambda p: p.stem) if meta_dir.exists() else []
        if not meta_files:
            meta_files = sorted(out_viet_dir.glob("*_meta.json"), key=lambda p: p.stem)
        if not meta_files:
            print(f"[!] Không tìm thấy dữ liệu OCR trong {meta_dir} hoặc {out_viet_dir}")
            return
            
        corrector = get_corrector()
        drop_log, seen = [], set()
        th_lines, tpa_lines, tdn_lines = [], [], []
        for mf in meta_files:
            doc_id = mf.stem.replace("_meta", "")
            try:
                mdata = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                continue
            han_txt = mdata.get("han_raw", "")
            if not han_txt:
                hf = out_han_dir / f"{doc_id}.txt"
                if hf.exists():
                    han_txt = hf.read_text(encoding="utf-8")
            pa_txt = mdata.get("pa", "")
            dn_txt = mdata.get("dn", "")
            # Tính lại từ OCR thô (không dùng han_clean cache cũ có thể chứa chữ đoán theo âm)
            seen.add(doc_id)
            han_txt, _ = build_han_clean(corrector, han_txt, mdata.get("han_boxes", []), pa_txt, doc_id, drop_log)

            clean_han = format_han_content(han_txt)
            clean_pa = format_phien_am_content(pa_txt)
            clean_dn = format_dich_nghia_content(dn_txt)
            
            th_lines.append(f"### {doc_id}\n{clean_han}\n")
            tpa_lines.append(f"### {doc_id}\n{clean_pa}\n")
            tdn_lines.append(f"### {doc_id}\n{clean_dn}\n")
            
        (out_text_dir / "han.txt").write_text("\n".join(th_lines) + "\n", encoding="utf-8")
        (out_text_dir / "phien_am.txt").write_text("\n".join(tpa_lines) + "\n", encoding="utf-8")
        (out_text_dir / "dich_nghia.txt").write_text("\n".join(tdn_lines) + "\n", encoding="utf-8")
        write_drop_log(ma_sach, drop_log, seen)
        print(f"[✓] Đã chuẩn hóa thành công {len(th_lines)} văn bản theo 100% Quy ước nội dung!")
        print(f"    - {out_text_dir / 'han.txt'}")
        print(f"    - {out_text_dir / 'phien_am.txt'}")
        print(f"    - {out_text_dir / 'dich_nghia.txt'}")
        return
    
    # 1. Xác định số trang của file PDF
    args.pdf = str(resolve_pdf(args.pdf))
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
    first_page_of_book = 5 if ma_sach == "R1003" else 4
    is_resume = start_p > first_page_of_book
    existing_docs = list((out_dir / "02_ocr_tho" / "han").glob(f"{ma_sach}.*_1.jpg")) if (out_dir / "02_ocr_tho" / "han").exists() else []
    if existing_docs and is_resume:
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
    drop_log = []

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
        meta_dir = cache_dir / "meta"
        meta_dir.mkdir(parents=True, exist_ok=True)
        meta_file = meta_dir / f"{doc_id}_meta.json"
        legacy_meta = out_viet_dir / f"{doc_id}_meta.json"
        if not meta_file.exists() and legacy_meta.exists():
            meta_file = legacy_meta
        han_file = out_han_dir / f"{doc_id}.txt"
        viet_file = out_viet_dir / f"{doc_id}.txt"
        
        viet_img_rel = f"viet/{doc_id}_1.jpg"
        han_img_rel = f"han/{doc_id}_1.jpg"

        if not args.force and meta_file.exists() and han_file.exists() and viet_file.exists():
            print(f"  -> [{i+1}/{len(all_docs)}] Đã có sẵn dữ liệu OCR cho {doc_id} (Trang {doc['page_num']}) -> Tái sử dụng.")
            try:
                mdata = json.loads(meta_file.read_text(encoding="utf-8"))
                pa_txt = mdata.get("pa", "")
                # Tính lại từ OCR thô thay vì dùng han_clean đã cache (cache cũ có thể chứa chữ đoán hoặc toàn □)
                han_txt = mdata.get("han_raw") or han_file.read_text(encoding="utf-8")
                dn_txt = mdata.get("dn", "")
                vi_boxes = mdata.get("vi_boxes", [])
                han_boxes = mdata.get("han_boxes", [])
                corr_han_txt, _ = build_han_clean(corrector, han_txt, han_boxes, pa_txt, doc_id, drop_log)
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
            
            # Lọc dòng rác rồi sửa chữ giống hình (không đoán chữ theo âm) — xem build_han_clean
            corr_han_txt, details = build_han_clean(corrector, han_txt, han_boxes, pa_txt, doc_id, drop_log)
            n_ok = sum(1 for d in details if syl_key(d['syllable']) in corrector.han_readings.get(d['char'], ()))
            acc = (n_ok / len(details) * 100) if details else 0
            print(f"      [Auto-Correction] Chữ Hán khớp âm từ điển: {n_ok}/{len(details)} ({acc:.1f}%)")
            
            # Lưu file OCR thô chữ Hán nguyên trạng vào 02_ocr_tho/han/<doc_id>.txt (chuẩn hợp đồng: không sửa tay)
            han_file.write_text(han_txt, encoding="utf-8")
            
            # Lưu meta cache để resume
            meta_file.write_text(json.dumps({
                "han_raw": han_txt,
                "han_clean": corr_han_txt,
                "pa": pa_txt,
                "dn": dn_txt,
                "vi_boxes": vi_boxes,
                "han_boxes": han_boxes
            }, ensure_ascii=False), encoding="utf-8")
        
        # Ghi Label.txt theo format: <folder>/<image>\t<json_boxes>
        viet_label_lines.append(f"{viet_img_rel}\t{json.dumps(vi_boxes, ensure_ascii=False)}")
        viet_filestate_lines.append(f"{viet_img_rel}\t1")
        han_label_lines.append(f"{han_img_rel}\t{json.dumps(label_boxes(han_boxes), ensure_ascii=False)}")
        han_filestate_lines.append(f"{han_img_rel}\t1")
        
        # Tích lũy cho 03_text_sach/ (Tự động chuẩn hóa 100% theo đúng Quy ước nội dung của Thầy Cô)
        clean_han = format_han_content(corr_han_txt if corr_han_txt else han_txt)
        clean_pa = format_phien_am_content(pa_txt)
        clean_dn = format_dich_nghia_content(dn_txt)
        
        text_sach_han.append(f"### {doc_id}\n{clean_han}\n")
        text_sach_pa.append(f"### {doc_id}\n{clean_pa}\n")
        text_sach_dn.append(f"### {doc_id}\n{clean_dn}\n")
        
        # Ghi file định kỳ sau mỗi 10 văn bản hoặc văn bản cuối cùng để chống mất dữ liệu
        if (i + 1) % 10 == 0 or (i + 1) == len(all_docs):
            if not is_resume:
                (out_viet_dir / "Label.txt").write_text("\n".join(viet_label_lines) + "\n", encoding="utf-8")
                (out_viet_dir / "fileState.txt").write_text("\n".join(viet_filestate_lines) + "\n", encoding="utf-8")
                (out_han_dir / "Label.txt").write_text("\n".join(han_label_lines) + "\n", encoding="utf-8")
                (out_han_dir / "fileState.txt").write_text("\n".join(han_filestate_lines) + "\n", encoding="utf-8")
                (out_text_dir / "han.txt").write_text("\n".join(text_sach_han) + "\n", encoding="utf-8")
                (out_text_dir / "phien_am.txt").write_text("\n".join(text_sach_pa) + "\n", encoding="utf-8")
                (out_text_dir / "dich_nghia.txt").write_text("\n".join(text_sach_dn) + "\n", encoding="utf-8")
        
    # Ghi file Label.txt, fileState.txt và 03_text_sach (tự động append nếu chạy theo từng cụm trang)
    def append_or_write(filepath, new_lines):
        if filepath.exists() and is_resume:
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
    write_drop_log(ma_sach, drop_log, {d["doc_id"] for d in all_docs})

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

