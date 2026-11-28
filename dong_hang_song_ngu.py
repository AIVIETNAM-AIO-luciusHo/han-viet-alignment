"""
dong_hang_song_ngu.py — dóng hàng Hán ↔ dịch nghĩa cho text song ngữ sạch, đã chia đoạn, không phiên âm
(vd Tư trị thông giám: 128.han.txt / 128.viet.txt).

Đầu vào: 2 file .txt trong một thư mục con bất kỳ của thư mục sách, script tự tìm theo tên file:
    <MA_SACH>/<thư mục con>/xxx.han.txt     (tên có 'han')
    <MA_SACH>/<thư mục con>/xxx.viet.txt    (tên có 'viet' hoặc 'dich_nghia')
    vd R13128/data/128.han.txt + R13128/data/128.viet.txt
Mỗi dòng không rỗng là một đoạn; đoạn bên Hán đi theo thứ tự đoạn bên Việt. Script chép 2 file vào
<MA_SACH>/03_text_sach/{han,dich_nghia}.txt (theo docs/contract.md) rồi dóng hàng. Có thể chỉ rõ bằng --han/--viet.
Đầu ra:
    <MA_SACH>/04_dong_hang/<MA_SACH>_parallel.tsv / .xlsx   (7 cột theo docs/contract.md, phien_am trống)
    workspace/<MA_SACH>/review_song_ngu.tsv                 (kiểu ghép, số mốc, cảnh báo từng cặp)

Cách dùng:
    # 2 file .txt đã đặt trong R13128/<thư mục con>/
    python dong_hang_song_ngu.py --ma-sach R13128

    # hoặc chỉ rõ file
    python dong_hang_song_ngu.py --ma-sach R13128 --han C:/Users/.../128.han.txt --viet C:/Users/.../128.viet.txt

    # chạy lại, ghi đè bản cũ (MẤT bản sửa tay)
    python dong_hang_song_ngu.py --ma-sach R13128 --force

    # sau khi sửa tay .xlsx: ghi lại TSV từ XLSX rồi kiểm tra
    python dong_hang_song_ngu.py --ma-sach R13128 --sync xlsx
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from han_viet_alignment.alignment.pipeline import COLUMNS  # noqa: E402
from han_viet_alignment.common.dictionary import DEFAULT_DICT, load_readings  # noqa: E402
from han_viet_alignment.export.writer import write_tsv, write_xlsx  # noqa: E402
from han_viet_alignment.song_ngu.align import align_text, n_han, n_syl, warnings  # noqa: E402

CHECKER = ROOT / "guideline" / "mau_du_lieu" / "kiem_tra_du_lieu.py"
REVIEW_COLUMNS = ["sent_id", "co", "kieu", "so_chu_han", "so_am_tiet", "moc", "canh_bao"]


_HAN_NAME = re.compile(r"(^|[._\- ])(han|hán)($|[._\- ])", re.I)
_VIET_NAME = re.compile(r"(^|[._\- ])(viet|việt|vi|dich|dịch|dich_nghia|dịch_nghĩa)($|[._\- ])", re.I)
_SKIP_DIRS = {"04_dong_hang", "03_text_sach"}


def find_inputs(bdir: Path) -> dict[str, str]:
    """Tìm cặp file .txt (Hán, Việt) trong các thư mục con của thư mục sách.

    Tên file phải có chữ 'han' (vd 128.han.txt, han.txt) hoặc 'viet'/'dich_nghia' (vd 128.viet.txt, dich_nghia.txt).
    Ưu tiên file trong thư mục dữ liệu của bạn; chỉ khi không có mới dùng 03_text_sach/ (bản đã chép lần trước).
    """
    if not bdir.is_dir():
        sys.exit(f"[!] Không có thư mục sách {bdir}. Tạo {bdir}/<thư mục con>/ và đặt 2 file .txt vào đó.")
    txts = [p for p in bdir.rglob("*.txt")]
    data = [p for p in txts if not _SKIP_DIRS & set(p.relative_to(bdir).parts[:-1])]
    for pool in (data, [p for p in txts if p.parent.name == "03_text_sach"]):
        han = [p for p in pool if _HAN_NAME.search(p.stem)]
        viet = [p for p in pool if _VIET_NAME.search(p.stem)]
        if not han and not viet:
            continue
        if len(han) != 1 or len(viet) != 1:
            sys.exit("[!] Cần đúng 1 file Hán và 1 file Việt trong " + str(bdir)
                     + f"\n    Hán tìm thấy: {[str(p) for p in han]}\n    Việt tìm thấy: {[str(p) for p in viet]}"
                     + "\n    Đặt tên kiểu 128.han.txt / 128.viet.txt, hoặc chỉ rõ bằng --han/--viet.")
        print(f"Tìm thấy: Hán = {han[0]}\n          Việt = {viet[0]}")
        return {"han": str(han[0]), "viet": str(viet[0])}
    sys.exit(f"[!] Không thấy file .txt nào trong các thư mục con của {bdir}.\n"
             f"    Đặt 2 file (vd {bdir.name}/data/128.han.txt và 128.viet.txt) hoặc dùng --han/--viet.")


def run_checker(tsv: Path, xlsx: Path, dict_path: str) -> int:
    if not CHECKER.exists():
        print(f"[!] Không thấy {CHECKER} — bỏ qua bước kiểm tra chính thức.")
        return 0
    print(f"\n[KIỂM TRA] {CHECKER.name}")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}  # Windows: tránh lỗi cp1252 khi in tiếng Việt
    return subprocess.call([sys.executable, str(CHECKER), str(tsv), "--dict", dict_path, "--xlsx", str(xlsx)],
                           env=env)


def sync_from_xlsx(tsv: Path, xlsx: Path) -> None:
    from openpyxl import load_workbook
    ws = load_workbook(xlsx, read_only=True)["DONG_HANG"]
    it = ws.iter_rows(values_only=True)
    head = [str(c) for c in next(it)]
    rows = [{c: ("" if v is None else str(v)) for c, v in zip(head, r)} for r in it if any(r)]
    write_tsv(tsv, rows, COLUMNS)
    write_xlsx(xlsx, rows, COLUMNS)
    print(f"Đã ghi lại {tsv.name} và {xlsx.name} từ XLSX ({len(rows)} cặp).")


def sync_from_tsv(tsv: Path, xlsx: Path) -> None:
    with tsv.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))
    write_tsv(tsv, rows, COLUMNS)
    write_xlsx(xlsx, rows, COLUMNS)
    print(f"Đã chuẩn hóa {tsv.name} và ghi lại {xlsx.name} ({len(rows)} cặp).")


def main() -> None:
    ap = argparse.ArgumentParser(description="Dóng hàng Hán ↔ dịch nghĩa cho text song ngữ đã chia đoạn")
    ap.add_argument("--ma-sach", required=True, help="Mã sách, vd R13128 (dùng làm tiền tố doc_id/sent_id)")
    ap.add_argument("--book-dir", default=None, help="Thư mục sách (mặc định ./<ma-sach>)")
    ap.add_argument("--han", default=None, help="File chữ Hán; chép vào <book-dir>/03_text_sach/han.txt")
    ap.add_argument("--viet", default=None, help="File bản dịch; chép vào <book-dir>/03_text_sach/dich_nghia.txt")
    ap.add_argument("--dict", default=str(DEFAULT_DICT))
    ap.add_argument("--doc-type", default="khac", help="Giá trị cột doc_type (mặc định khac)")
    ap.add_argument("--force", action="store_true", help="Ghi đè 04_dong_hang đã có dữ liệu (MẤT bản sửa tay)")
    ap.add_argument("--sync", choices=["xlsx", "tsv"], help="Sau khi sửa tay: ghi lại cả hai file từ file này")
    ap.add_argument("--no-check", action="store_true", help="Bỏ qua kiem_tra_du_lieu.py")
    args = ap.parse_args()

    book = args.ma_sach
    bdir = Path(args.book_dir or ROOT / book)
    text_dir = bdir / "03_text_sach"
    out_tsv = bdir / "04_dong_hang" / f"{book}_parallel.tsv"
    out_xlsx = out_tsv.with_suffix(".xlsx")

    if args.sync:
        src = out_xlsx if args.sync == "xlsx" else out_tsv
        if not src.exists():
            sys.exit(f"[!] Không có {src}")
        (sync_from_xlsx if args.sync == "xlsx" else sync_from_tsv)(out_tsv, out_xlsx)
        if not args.no_check:
            sys.exit(run_checker(out_tsv, out_xlsx, args.dict))
        return

    if not (args.han and args.viet):
        found = find_inputs(bdir)
        args.han = args.han or found["han"]
        args.viet = args.viet or found["viet"]
    text_dir.mkdir(parents=True, exist_ok=True)
    for given, name in ((args.han, "han.txt"), (args.viet, "dich_nghia.txt")):
        dst = text_dir / name
        if Path(given).resolve() != dst.resolve():
            shutil.copyfile(given, dst)
            print(f"Chép {given} -> {dst}")
        else:
            print(f"Dùng {dst}")
    han_path, dn_path = text_dir / "han.txt", text_dir / "dich_nghia.txt"

    if out_tsv.exists() and sum(1 for _ in out_tsv.open(encoding="utf-8")) > 1 and not args.force:
        sys.exit(f"[!] {out_tsv} đã có dữ liệu. Thêm --force để ghi đè (mất bản sửa tay).")

    print("Nạp từ điển âm Hán-Việt ...")
    readings = load_readings(args.dict)
    pairs, st = align_text(han_path.read_text(encoding="utf-8"), dn_path.read_text(encoding="utf-8"), readings)
    print(f"[{book}] Đoạn: Hán {st['han_paras']}, Việt {st['viet_paras']} "
          f"(+{st['headers']} dòng tiêu đề Hán-Việt tách riêng); tỷ lệ âm tiết/chữ = {st['ratio']:.3f}")
    if st["para_not_1_1"]:
        print(f"[{book}] Nhóm đoạn không 1:1 (Hán từ–đến, Việt từ–đến): {st['para_not_1_1']}")

    rows, review, counter = [], [], Counter()
    for p in pairs:
        doc = f"{book}.{p.group:03d}"
        counter[doc] += 1
        sid = f"{doc}.{counter[doc]}"
        rows.append({"sent_id": sid, "doc_id": doc, "doc_type": args.doc_type, "han": p.han, "phien_am": "",
                     "dich_nghia": p.viet, "ghi_chu": p.note})
        w = warnings(p, st["ratio"])
        review.append({"sent_id": sid, "co": "x" if w else "", "kieu": p.kind, "so_chu_han": str(n_han(p.han)),
                       "so_am_tiet": str(n_syl(p.viet)), "moc": str(p.lex), "canh_bao": " ".join(w)})

    write_tsv(out_tsv, rows, COLUMNS)
    write_xlsx(out_xlsx, rows, COLUMNS)
    rv = ROOT / "workspace" / book / "review_song_ngu.tsv"
    write_tsv(rv, review, REVIEW_COLUMNS)

    kinds = Counter(r["kieu"] for r in review)
    print(f"[{book}] {len(rows)} cặp; kiểu: {dict(kinds.most_common())}")
    print(f"[{book}] Cặp có cảnh báo: {sum(1 for r in review if r['co'])} (xem {rv})")
    print(f"[{book}] Ghi {out_tsv}\n[{book}] Ghi {out_xlsx}")
    if not args.no_check:
        sys.exit(run_checker(out_tsv, out_xlsx, args.dict))


if __name__ == "__main__":
    main()
