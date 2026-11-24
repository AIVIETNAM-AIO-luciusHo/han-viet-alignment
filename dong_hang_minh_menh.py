"""
dong_hang_minh_menh.py — dóng hàng Hán ↔ dịch nghĩa cho Minh Mệnh chính yếu (R1204–R1206, không phiên âm).

Đầu vào trong thư mục sách:
    02_ocr_tho/han/<MA_SACH>_han_ppocrv6.md          OCR chữ Hán theo trang PDF ("## Trang N")
    02_ocr_tho/viet/<MA_SACH>_dich_nghia_sach.md     lớp chữ PDF bản dịch, còn mốc "[tờ 12-a]"
    03_text_sach/dich_nghia.txt                      bản dịch đã chia văn bản ("### <doc_id>")
Đầu ra:
    04_dong_hang/<MA_SACH>_parallel.tsv / .xlsx     (phien_am để trống theo docs/contract.md)
    workspace/<MA_SACH>/review_minh_menh.tsv         chỉ số từng cặp + cảnh báo để người kiểm tra
    workspace/<MA_SACH>/han_bi_loai.tsv              dòng OCR Hán bị lọc (lề trang, nhiễu) hoặc không ghép được

Cách dùng:
    python dong_hang_minh_menh.py --ma-sach R1204 --book-dir "C:/Users/.../Downloads/R1204"
    # Chỉ giữ cặp tin cậy (cặp bị loại -> workspace/<MA_SACH>/cap_bi_loai.tsv để sửa tay)
    python dong_hang_minh_menh.py --ma-sach R1204 --book-dir ... --force --loc-tin-cay
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys

import numpy as np
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from han_viet_alignment.alignment.pipeline import COLUMNS  # noqa: E402
from han_viet_alignment.common.dictionary import DEFAULT_DICT, load_readings  # noqa: E402
from han_viet_alignment.common.text import read_blocks, syllables, write_blocks  # noqa: E402
from han_viet_alignment.export.writer import write_tsv, write_xlsx  # noqa: E402
from han_viet_alignment.minh_menh.align import (  # noqa: E402
    align_quyen, align_stream, build_stream, group_sentences, rough_cuts, split_by_quyen)
from han_viet_alignment.minh_menh.han_ocr import SHEET, folio_label, load_han_book  # noqa: E402
from han_viet_alignment.minh_menh.viet_text import (  # noqa: E402
    anchor_positions, assign_folios, build_sentences, parse_markers, segment_translation, sentence_tokens)

REVIEW_COLUMNS = ["sent_id", "co", "so_chu_han", "so_am_tiet", "ty_le", "bien_do",
                  "to_han", "to_dich", "so_cau_dich", "canh_bao"]
NGUONG_GOP = {"R1204": 1.25, "R1205": 1.25, "R1206": 1.75}
NGUONG_GOP_MAC_DINH = 1.5


def doc_types(book: str) -> dict[str, str]:
    path = ROOT / "metadata" / "documents.tsv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {r["doc_id"]: r["doc_type"] for r in csv.DictReader(f, delimiter="\t") if r["book_id"] == book}


def main() -> None:
    ap = argparse.ArgumentParser(description="Dóng hàng Hán ↔ dịch nghĩa cho sách Minh Mệnh (không phiên âm)")
    ap.add_argument("--ma-sach", required=True)
    ap.add_argument("--book-dir", default=None, help="Thư mục sách (mặc định ./<ma-sach>)")
    ap.add_argument("--dict", default=str(DEFAULT_DICT))
    ap.add_argument("--force", action="store_true", help="Ghi đè 04_dong_hang đã có dữ liệu (MẤT bản sửa tay)")
    ap.add_argument("--loc-tin-cay", action="store_true",
                    help="Chỉ giữ cặp tin cậy trong file bàn giao; cặp kém tin cậy ghi ra workspace/<MA_SACH>/cap_bi_loai.tsv")
    ap.add_argument("--nguong-gop", type=float, default=None,
                    help="Biên độ tối thiểu để tách hai câu dịch thành hai cặp; thấp hơn thì gộp (cao = ít cặp, ít lỗi)")
    args = ap.parse_args()

    book = args.ma_sach
    if args.nguong_gop is None:
        args.nguong_gop = NGUONG_GOP.get(book, NGUONG_GOP_MAC_DINH)
    bdir = Path(args.book_dir or ROOT / book)
    han_md = (bdir / "02_ocr_tho" / "han" / f"{book}_han_ppocrv6.md").read_text(encoding="utf-8")
    viet_md = (bdir / "02_ocr_tho" / "viet" / f"{book}_dich_nghia_sach.md").read_text(encoding="utf-8")
    dn_path = bdir / "03_text_sach" / "dich_nghia.txt"
    if not dn_path.exists():
        docs = segment_translation(viet_md)
        if not docs:
            sys.exit(f"[!] Thiếu {dn_path} và không chia được bản dịch từ {book}_dich_nghia_sach.md.")
        ids = [f"{book}.{k:03d}" for k in range(1, len(docs) + 1)]
        dn_path.parent.mkdir(parents=True, exist_ok=True)
        write_blocks(dn_path, dict(zip(ids, docs)))
        write_blocks(dn_path.with_name("phien_am.txt"), {i: "" for i in ids})
        print(f"[{book}] Chưa có dich_nghia.txt: đã chia tự động {len(docs)} văn bản -> {dn_path} "
              f"(cần người rà ranh giới văn bản; phien_am.txt để trống)")
    out_tsv = bdir / "04_dong_hang" / f"{book}_parallel.tsv"
    if out_tsv.exists() and sum(1 for _ in out_tsv.open(encoding="utf-8")) > 1 and not args.force:
        sys.exit(f"[!] {out_tsv} đã có dữ liệu. Thêm --force để ghi đè (mất bản sửa tay).")

    readings = load_readings(args.dict)
    hb = load_han_book(han_md)
    sents = build_sentences(read_blocks(dn_path))
    markers = parse_markers(viet_md)
    anchors = anchor_positions(viet_md, markers, sentence_tokens(sents))
    assign_folios(sents, anchors)
    print(f"[{book}] Hán: {len(hb.units)} đoạn, {sum(len(u.text) for u in hb.units)} chữ, "
          f"{len(hb.quyen_numbers)} quyển {list(hb.quyen_numbers.values())}; "
          f"lọc {len(hb.dropped)} dòng lề/nhiễu")
    print(f"[{book}] Dịch: {len({s.doc_id for s in sents})} văn bản, {len(sents)} câu; "
          f"mốc tờ đọc được {len(markers)}, neo được {len(anchors)}")

    ratio = sum(len(syllables(s.text)) for s in sents) / max(1, sum(len(u.text) for u in hb.units))
    types = doc_types(book)
    dropped = [(p, ln, r) for p, ln, r in hb.dropped]

    pairs: list[dict] = []
    for q, units, qsents in split_by_quyen(hb.units, sents):
        if not qsents:
            for u in units:
                dropped.append((u.pages[0], u.text, "khong_co_cau_dich"))
            continue
        if not units:
            continue
        st = build_stream(units)
        beads = align_quyen(units, qsents, readings, ratio)
        cuts, margins = align_stream(st, qsents, rough_cuts(units, qsents, beads, st), readings, ratio)
        unit_of = np.searchsorted(np.array(st.unit_start), np.arange(len(st.text) + 1), side="right") - 1
        for a, b in group_sentences(cuts, margins, args.nguong_gop):
            h0, h1 = cuts[a], cuts[b]
            if h1 <= h0:
                continue
            vs = qsents[a:b]
            u0, u1 = units[unit_of[h0]], units[unit_of[max(h0, h1 - 1)]]
            pairs.append({"han": st.text[h0:h1], "viet": vs, "doc_id": vs[0].doc_id, "q": q,
                          "fol": (u0.folio_start, u1.folio_end), "edge": min(margins[a], margins[b]),
                          "n_han": h1 - h0, "n_syl": sum(len(syllables(x.text)) for x in vs)})

    by_q: dict[int, list[float]] = {}
    for p in pairs:
        if p["n_han"] >= 20:
            by_q.setdefault(p["q"], []).append(p["n_syl"] / p["n_han"])
    q_ratio = {q: statistics.median(v) for q, v in by_q.items()}

    kept, removed = [], []
    for p in pairs:
        vs, nh, nv = p["viet"], p["n_han"], p["n_syl"]
        r = nv / max(nh, 1)
        docs = list(dict.fromkeys(s.doc_id for s in vs))
        warn = []
        if len(vs) > 1:
            warn.append(f"GOP_CAU({len(vs)})")
        if len(docs) > 1:
            warn.append("QUA_VAN_BAN")
        rel = r / max(q_ratio.get(p["q"], ratio), 1e-6)
        low = []
        if (rel > 1.8 or rel < 0.55) and not (len(vs) == 1 and vs[0].year):
            low.append("TIN_CAY_THAP:TY_LE")
        if p["edge"] < args.nguong_gop + 0.5:
            warn.append("RANH_GIOI_SAT_NGUONG")
        p["warn_all"], p["docs"], p["ratio"] = warn + low, docs, r
        (removed if (args.loc_tin_cay and low) else kept).append(p)

    def to_row(p: dict, sid: str) -> tuple[dict, dict]:
        vs = p["viet"]
        dn = " ".join(s.text for s in vs)
        notes = [s.note for s in vs if s.note]
        if len(p["docs"]) > 1:
            notes.append(f"Câu dịch gồm cả phần của {', '.join(p['docs'][1:])} (đoạn Hán không tách được).")
        row = {"sent_id": sid, "doc_id": p["doc_id"], "doc_type": types.get(p["doc_id"], "khac"), "han": p["han"],
               "phien_am": "", "dich_nghia": dn, "ghi_chu": " ".join(notes)}
        rev = {"sent_id": sid, "co": "x" if [w for w in p["warn_all"] if not w.startswith("GOP_CAU")] else "",
               "so_chu_han": str(p["n_han"]), "so_am_tiet": str(p["n_syl"]), "ty_le": f"{p['ratio']:.2f}",
               "bien_do": f"{p['edge']:.2f}",
               "to_han": f"{folio_label(p['fol'][0], hb.quyen_numbers)}–{folio_label(p['fol'][1], hb.quyen_numbers)}",
               "to_dich": f"{folio_label(vs[0].folio_start, hb.quyen_numbers)}–"
                          f"{folio_label(vs[-1].folio_end, hb.quyen_numbers)}",
               "so_cau_dich": str(len(vs)), "canh_bao": " ".join(p["warn_all"])}
        return row, rev

    rows, review, counter = [], [], {}
    for p in kept:
        doc = p["doc_id"]
        counter[doc] = counter.get(doc, 0) + 1
        row, rev = to_row(p, f"{doc}.{counter[doc]}")
        rows.append(row)
        review.append(rev)
    removed_rows = []
    for k, p in enumerate(removed, 1):
        row, rev = to_row(p, f"{p['doc_id']}.x{k}")
        removed_rows.append({**row, "ly_do_loai": rev["canh_bao"]})

    write_tsv(out_tsv, rows, COLUMNS)
    write_xlsx(out_tsv.with_suffix(".xlsx"), rows, COLUMNS)
    ws = ROOT / "workspace" / book
    write_tsv(ws / "review_minh_menh.tsv", review, REVIEW_COLUMNS)
    write_tsv(ws / "han_bi_loai.tsv", [{"trang": str(p), "dong_ocr": ln, "ly_do": r} for p, ln, r in dropped],
              ["trang", "dong_ocr", "ly_do"])
    if args.loc_tin_cay:
        write_tsv(ws / "cap_bi_loai.tsv", removed_rows, COLUMNS + ["ly_do_loai"])

    flagged = sum(1 for r in review if r["co"])
    n_sent_out = sum(len(p["viet"]) for p in kept)
    print(f"[{book}] Cặp: {len(rows)} (từ {n_sent_out}/{len(sents)} câu dịch, ngưỡng gộp {args.nguong_gop}) | "
          f"văn bản có cặp: {len(counter)} | tỷ lệ âm tiết/chữ Hán: {ratio:.2f} "
          f"(theo quyển: {', '.join(f'{hb.quyen_numbers[q]}={v:.2f}' for q, v in sorted(q_ratio.items()))})")
    if args.loc_tin_cay:
        print(f"  • Lọc tin cậy: giữ {len(kept)}, loại {len(removed)} cặp -> {ws / 'cap_bi_loai.tsv'} (sửa tay rồi bổ sung)")
    print(f"  • Cặp có cảnh báo cần xem: {flagged}")
    print("  • Độ khớp âm: không áp dụng (sách không có phiên âm)")
    print(f"  • Ghi: {out_tsv} (+ .xlsx), {ws / 'review_minh_menh.tsv'}, {ws / 'han_bi_loai.tsv'}")

if __name__ == "__main__":
    main()
