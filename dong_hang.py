"""
dong_hang.py — Người 2: làm sạch, tách câu, dóng hàng Hán – phiên âm – dịch nghĩa, xuất TSV/XLSX.

Đầu vào (do ocr_tho.py của Người 1 sinh ra):
    <MA_SACH>/03_text_sach/{han,phien_am,dich_nghia}.txt   (mỗi văn bản mở đầu '### <doc_id>')
    <MA_SACH>/02_ocr_tho/han/<doc_id>.txt                    (dự phòng khi han.txt hỏng)
Đầu ra:
    <MA_SACH>/04_dong_hang/<MA_SACH>_parallel.tsv / .xlsx   (bàn giao)
    workspace/<MA_SACH>/review.tsv                          (danh sách dòng cần người kiểm tra)

Cách dùng:
    # 1. Tạo bản nháp dóng hàng tự động
    python dong_hang.py --ma-sach R1001

    # 2. Sau khi sửa tay file .xlsx (hoặc .tsv): chuẩn hóa, ghi lại cả hai file, kiểm tra
    python dong_hang.py --ma-sach R1001 --sync xlsx

    # 3. Chỉ chạy kiểm tra trên file hiện có
    python dong_hang.py --ma-sach R1001 --check-only
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from han_viet_alignment.alignment.cleaning import clean_han, clean_phien_am  # noqa: E402
from han_viet_alignment.alignment.han_pa import match_score  # noqa: E402
from han_viet_alignment.alignment.pipeline import (  # noqa: E402
    COLUMNS, REVIEW_COLUMNS, DocInput, align_document, build_memory, summarize)
from han_viet_alignment.common.dictionary import DEFAULT_DICT, load_readings  # noqa: E402
from han_viet_alignment.common.text import MISSING, clean_cell, read_blocks  # noqa: E402
from han_viet_alignment.export.writer import write_tsv, write_xlsx  # noqa: E402

CHECKER = ROOT / "guideline" / "mau_du_lieu" / "kiem_tra_du_lieu.py"


def load_docs(book_dir: Path, han_source: str, readings=None) -> tuple[list[DocInput], list[str]]:
    text_dir = book_dir / "03_text_sach"
    han = read_blocks(text_dir / "han.txt")
    pa = read_blocks(text_dir / "phien_am.txt")
    dn = read_blocks(text_dir / "dich_nghia.txt")
    raw_dir = book_dir / "02_ocr_tho" / "han"
    notes, docs = [], []
    order = list(dict.fromkeys([*pa, *han, *dn]))  # thứ tự văn bản theo sách
    for doc_id in order:
        h = han.get(doc_id, "")
        raw_file = raw_dir / f"{doc_id}.txt"
        broken = not h or h.count(MISSING) > 0.5 * len(h)
        if han_source == "raw" and raw_file.exists():
            h = raw_file.read_text(encoding="utf-8")
        elif han_source == "auto" and raw_file.exists():
            raw = raw_file.read_text(encoding="utf-8")
            if readings is not None and pa.get(doc_id):
                # Có phiên âm: chọn nguồn khớp âm nhiều chữ hơn (độ khớp âm tính trên kết quả cuối).
                # So cả khi han.txt nhiều □: □ không được tính điểm, nên so vẫn công bằng.
                p_clean = clean_phien_am(pa[doc_id], readings)
                s_txt = match_score(clean_han(h), p_clean, readings)
                s_raw = match_score(clean_han(raw), p_clean, readings)
                if s_raw > s_txt or (s_raw == s_txt and broken):
                    notes.append(f"{doc_id}: dùng OCR thô {raw_file.relative_to(book_dir)} "
                                 f"(khớp âm {s_raw} chữ, han.txt {s_txt} chữ)")
                    h = raw
            elif broken:  # không có phiên âm để so: chỉ thay khi han.txt rỗng/toàn □
                notes.append(f"{doc_id}: han.txt rỗng/toàn □ -> dùng OCR thô {raw_file.relative_to(book_dir)}")
                h = raw
        docs.append(DocInput(doc_id, h, pa.get(doc_id, ""), dn.get(doc_id, "")))
    return docs, notes


def read_edited(path: Path) -> list[dict]:
    import pandas as pd
    if path.suffix == ".xlsx":
        df = pd.read_excel(path, sheet_name="DONG_HANG", dtype=str).fillna("")
    else:
        df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, quoting=3, encoding="utf-8")
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        sys.exit(f"[!] {path} thiếu cột {missing}")
    rows = [{c: clean_cell(str(r[c])) for c in COLUMNS} for _, r in df.iterrows()]
    return [r for r in rows if any(r.values())]  # bỏ dòng trống do sửa tay


def run_checker(tsv: Path, xlsx: Path, dict_path: Path) -> int:
    if not CHECKER.exists():
        print(f"[!] Không thấy script kiểm tra của giáo viên ở {CHECKER} — bỏ qua bước kiểm tra chính thức.")
        return 0
    print(f"\n[KIỂM TRA] {CHECKER.name}")
    return subprocess.call([sys.executable, str(CHECKER), str(tsv), "--dict", str(dict_path), "--xlsx", str(xlsx)])


def print_summary(s: dict) -> None:
    print(f"  • Văn bản: {s['docs']} | Cặp: {s['pairs']} | Cặp hợp lệ (không □/[...]): {s['valid_pairs']}")
    if s["rows_with_pa"]:
        print(f"  • Dòng khớp số chữ Hán = số âm tiết: {s['rows_count_match']}/{s['rows_with_pa']}")
        print(f"  • Độ khớp âm: {s['chars_ok']}/{s['chars_total']} = {s['reading_match']:.2f}% (yêu cầu ≥ 95%)")
    if s["simplified"]:
        rows = s["simplified_rows"]
        print(f"  • Chữ giản thể do OCR sinh ra (phải sửa về chữ gốc theo ảnh, HD mục 3): {s['simplified']} chữ ở "
              f"{len(rows)} dòng — {', '.join(rows[:15])}" + (" ..." if len(rows) > 15 else ""))


def main() -> None:
    ap = argparse.ArgumentParser(description="Dóng hàng Hán – phiên âm – dịch nghĩa và xuất TSV/XLSX")
    ap.add_argument("--ma-sach", required=True, help="Mã sách, vd R1001")
    ap.add_argument("--book-dir", default=None, help="Thư mục sách (mặc định ./<ma-sach>)")
    ap.add_argument("--dict", default=str(DEFAULT_DICT), help="Từ điển QuocNgu_SinoNom_TongHop3.xlsx")
    ap.add_argument("--han-source", choices=["auto", "text_sach", "raw"], default="auto",
                    help="Nguồn chữ Hán: 03_text_sach/han.txt, OCR thô, hoặc auto (dùng OCR thô khi han.txt hỏng)")
    ap.add_argument("--doc-type", default="sac_phong", help="doc_type mặc định khi không tự nhận ra")
    ap.add_argument("--force", action="store_true", help="Cho phép ghi đè 04_dong_hang đã có (MẤT bản sửa tay)")
    ap.add_argument("--sync", choices=["xlsx", "tsv"], help="Đọc bản đã sửa tay, chuẩn hóa rồi ghi lại cả TSV và XLSX")
    ap.add_argument("--check-only", action="store_true", help="Chỉ kiểm tra file hiện có")
    ap.add_argument("--no-check", action="store_true", help="Không chạy script kiểm tra của giáo viên")
    ap.add_argument("--no-correct", action="store_true",
                    help="Không tự sửa lỗi OCR (chữ Hán gần giống/cụm từ lặp, âm tiết phiên âm hỏng)")
    ap.add_argument("--no-mask", action="store_true",
                    help="Giữ chữ Hán OCR lệch âm thay vì ghi □ (độ khớp âm sẽ thấp hơn)")
    args = ap.parse_args()

    ma = args.ma_sach
    book_dir = Path(args.book_dir or ma)
    out_dir = book_dir / "04_dong_hang"
    tsv, xlsx = out_dir / f"{ma}_parallel.tsv", out_dir / f"{ma}_parallel.xlsx"
    review_path = ROOT / "workspace" / ma / "review.tsv"
    readings = load_readings(args.dict)

    print("=" * 70)
    print(f"DÓNG HÀNG HÁN – PHIÊN ÂM – DỊCH NGHĨA ({ma})")
    print("=" * 70)

    if args.check_only:
        sys.exit(run_checker(tsv, xlsx, Path(args.dict)))

    if args.sync:
        src = xlsx if args.sync == "xlsx" else tsv
        rows = read_edited(src)
        write_tsv(tsv, rows, COLUMNS)
        write_xlsx(xlsx, rows, COLUMNS)
        print(f"[✓] Đã đồng bộ {len(rows)} dòng từ {src.name} sang TSV + XLSX")
        print_summary(summarize(rows, readings))
        sys.exit(0 if args.no_check else run_checker(tsv, xlsx, Path(args.dict)))

    if (tsv.exists() or xlsx.exists()) and not args.force:
        sys.exit(f"[!] {out_dir} đã có file dóng hàng. Nếu đã sửa tay, dùng --sync xlsx; "
                 f"muốn tạo lại bản nháp (ghi đè) thì thêm --force.")

    docs, notes = load_docs(book_dir, args.han_source, readings)
    if not docs:
        sys.exit(f"[!] Không có văn bản nào trong {book_dir / '03_text_sach'}")
    for n in notes:
        print("[*]", n)

    memory = None if args.no_correct else build_memory(docs, readings)
    rows, review = [], []
    for d in docs:
        r, rv = align_document(d, readings, args.doc_type, memory=memory,
                               correct=not args.no_correct, mask=not args.no_mask)
        rows.extend(r)
        review.extend(rv)
        flagged = sum(1 for x in rv if x["co"])
        print(f"  -> {d.doc_id}: {len(r)} cặp" + (f", {flagged} dòng cần kiểm tra" if flagged else ""))

    write_tsv(tsv, rows, COLUMNS)
    write_xlsx(xlsx, rows, COLUMNS)
    write_tsv(review_path, review, REVIEW_COLUMNS)
    print(f"\n[✓] {tsv}\n[✓] {xlsx}\n[✓] {review_path} (danh sách dòng cần người hiệu đính)")
    print_summary(summarize(rows, readings))
    # Tỷ lệ lỗi (HD mục 8) tính trên cặp hợp lệ: liệt kê cặp hợp lệ có dấu hiệu dóng lệch để rà trước
    risky = [rv["sent_id"] for r, rv in zip(rows, review)
             if MISSING not in r["han"] + r["phien_am"] and "[...]" not in r["dich_nghia"]
             and any(k in rv["canh_bao"] for k in ("LECH_", "THIEU_TEN", "GOP_NHIEU_CAU", "KHOP_AM", "GIAN_THE"))]
    print(f"  • Cặp hợp lệ có dấu hiệu lỗi dóng hàng (cần rà, mục tiêu tỷ lệ lỗi ≤ 20%): {len(risky)}"
          + (f" — {', '.join(risky[:15])}" + (" ..." if len(risky) > 15 else "") if risky else ""))
    if not args.no_check:
        run_checker(tsv, xlsx, Path(args.dict))


if __name__ == "__main__":
    main()
