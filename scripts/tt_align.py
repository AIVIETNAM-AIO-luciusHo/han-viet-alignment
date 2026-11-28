#!/usr/bin/env python3
"""P11-1: align docs-local/12x.han.txt / .viet.txt (clean text, temporary labels T122/T123/T124). Run with .venv-ocr/bin/python
(the dictionary is an .xlsx). Writes workspace/pkg/T12x/pairs_draft.tsv, khong_dong.tsv, report.txt and
workspace/review/T12x_review.html (review tool, same format as P9/P10). No LLM, no API, no network, texts never edited."""
import argparse
import csv
import glob
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from han_viet_alignment.minh_menh import han_docs as D  # noqa: E402
from han_viet_alignment.minh_menh import tt_align as T  # noqa: E402

HEAD_RE = re.compile(r"^([一-鿿]{1,5})(Năm .+)$")
PAIR_COLS = ["stt", "nhan_tam", "doan", "dong_viet", "dong_han", "van_ban_viet", "van_ban_han", "so_chu_han", "so_am_tiet_viet",
             "diem", "co", "ghi_chu", "x", "y", "trang_viet"]


def write_tsv(path, cols, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_NONE, quotechar=None, escapechar=None)
        w.writerow(cols)
        for r in rows:
            w.writerow([str(r[c]).replace("\t", " ").replace("\n", " ") for c in cols])


def run(n: str, scorer_for, review_dir: Path):
    label = f"T{n}"
    han_txt = (ROOT / "docs-local" / f"{n}.han.txt").read_text(encoding="utf-8")
    vie_txt = (ROOT / "docs-local" / f"{n}.viet.txt").read_text(encoding="utf-8")
    hp, vp = T.read_paras(han_txt), T.read_paras(vie_txt)
    scorer = scorer_for(hp)
    # header + title lines: own pairs
    fixed = [(hp[0], vp[0], "dong_dau", "dong 'Bat dau tu nam ... tat ca N nam' (khong phai van ban chinh)"),
             (hp[1], vp[1], "tieu_de", "dong tieu de phan/doan")]
    hb, vb = hp[2:], vp[2:]
    heads = []  # Vietnamese year-heading lines carrying their own Han ('九年Năm Nguyên Gia thứ 9'), not present in the .han file
    vbody = []
    for ln, t in vb:
        m = HEAD_RE.match(t)
        if m:
            heads.append((len(vbody), ln, t, m))
        else:
            vbody.append((ln, t))
    H = [t for _, t in hb]
    V = [D.viet_syllables(t) for _, t in vbody]
    ratio = sum(map(len, H)) / max(1, sum(map(len, V)))
    blocks = T.align_paras(H, V, scorer, ratio)
    pairs, unal = [], []
    cursor = 0  # offset in the Han stream (concatenation of ALL Han lines in file order)
    stream = []
    off = {}
    pos = 0
    for k, (ln, t) in enumerate(hp):
        off[ln] = pos
        pos += len(t)
        stream.append(t)
    Hs = "".join(stream)

    def add(vtext, htext, dong_v, dong_h, doan, co, note, x, y, sy):
        M = scorer.matched(D.viet_syllables(vtext))
        p0 = scorer.p0(M)
        rate = sum(c in M for c in htext) / len(htext) if htext else 0.0
        flags = list(co)
        if htext and sy and not (0.4 <= len(htext) / max(1.0, ratio * sy) <= 2.5):
            flags.append("lech_do_dai")
        if htext and rate < p0 + 0.35 * (scorer.p1 - p0):
            flags.append("diem_tu_vung_thap")
        pairs.append({"nhan_tam": f"{label}.{len(pairs) + 1:04d}", "doan": doan, "dong_viet": dong_v, "dong_han": dong_h, "van_ban_viet": vtext,
                      "van_ban_han": htext, "so_chu_han": len(htext), "so_am_tiet_viet": sy, "diem": f"{rate - p0:.3f}", "co": ",".join(flags),
                      "ghi_chu": note, "x": x, "y": y, "trang_viet": dong_v})

    for (hl, ht), (vl, vt), flag, note in fixed:
        add(vt, ht, vl, hl, flag, [flag], note, off[hl], off[hl] + len(ht), len(D.viet_syllables(vt)))
    head_at = {}
    for idx, ln, t, m in heads:
        head_at.setdefault(idx, []).append((ln, t, m))
    n_blocks = Counter()
    para_stats = {"cau_bang_nhau": 0, "cau_lech": 0}
    odd = []
    for bi, (h0, h1, v0, v1) in enumerate(blocks, 1):
        for vi in range(v0, v1 + 1):  # heading lines that sit before Viet paragraph vi
            pass
        doan = f"{label}.D{bi:03d}"
        for idx in sorted(head_at):
            if v0 <= idx < v1 + (1 if v1 == v0 else 0) and idx == v0:
                pass
        for idx in [i for i in sorted(head_at) if i == v0]:
            for ln, t, m in head_at.pop(idx):
                add(m.group(2), m.group(1), ln, "", doan, ["tieu_de_nam"], "Han lay tu chinh dong Viet (file .han khong co dong nay); khong thuoc luong than Han", -1, -1,
                    len(D.viet_syllables(m.group(2))))
        if h0 == h1:
            for ln, t in vbody[v0:v1]:
                unal.append({"nguon": "viet", "dong": ln, "ly_do": "khong_co_doan_Han", "van_ban": t})
            continue
        if v0 == v1:
            for ln, t in hb[h0:h1]:
                unal.append({"nguon": "han", "dong": ln, "ly_do": "khong_co_doan_Viet", "van_ban": t})
            continue
        n_blocks[(h1 - h0, v1 - v0)] += 1
        # sentences of the block
        hs, vs = [], []
        for k in range(h0, h1):
            ln, t = hb[k]
            hs += [(ln, off[ln] + a, off[ln] + b, t[a:b]) for a, b in T.split_han(t)]
        for k in range(v0, v1):
            ln, t = vbody[k]
            vs += [(ln, t[a:b]) for a, b in T.split_viet(t)]
        hsyl = [x[3] for x in hs]
        vsyl = [D.viet_syllables(x[1]) for x in vs]
        eq = len(hs) == len(vs)
        para_stats["cau_bang_nhau" if eq else "cau_lech"] += 1
        if not eq:
            odd.append((doan, hb[h0][0], vbody[v0][0], len(hs), len(vs)))
        sub = T.align_sentences(hsyl, vsyl, scorer, ratio)
        for a0, a1, b0, b1 in sub:
            co = []
            if h1 - h0 != v1 - v0:
                co.append("khoi_doan_%d_%d" % (h1 - h0, v1 - v0))
            if not eq:
                co.append("doan_lech_so_cau")
            if (a1 - a0, b1 - b0) != (1, 1):
                co.append("gop_%d_%d" % (a1 - a0, b1 - b0))
            if a0 == a1 or b0 == b1:
                co.append("cau_khong_doi")
            hx = hs[a0][1] if a1 > a0 else None
            hy = hs[a1 - 1][2] if a1 > a0 else None
            contiguous = all(hs[k][2] == hs[k + 1][1] for k in range(a0, a1 - 1))
            if not contiguous:
                co.append("han_khong_lien_tuc")  # sentences from two lines: the Han slice between them is not contiguous in the stream
            vtext = " ".join(vs[k][1] for k in range(b0, b1))
            htext = "".join(hs[k][3] for k in range(a0, a1))
            sy = len(D.viet_syllables(vtext))
            add(vtext, htext, vs[b0][0] if b1 > b0 else "", hs[a0][0] if a1 > a0 else "", doan, co, "", hx if hx is not None else -1,
                hy if hy is not None else -1, sy)
    for p in pairs:  # the Han of a pair spanning a line break is not one slice of the stream: mark such pairs for the review tool
        pass
    for i, p in enumerate(pairs, 1):
        p["stt"] = i
    # ---- reconstruction checks (0 lost / repeated characters)
    han_rebuilt = "".join(p["van_ban_han"] for p in pairs if "tieu_de_nam" not in p["co"])
    han_orig = "".join(t for _, t in hp if True)
    skipped_han = "".join(r["van_ban"] for r in unal if r["nguon"] == "han")
    ws = lambda s: re.sub(r"\s+", "", s)  # noqa: E731
    ok_han = sorted(han_rebuilt + skipped_han) == sorted(han_orig)
    vi_rebuilt = ws("".join(p["van_ban_viet"] for p in pairs if "tieu_de_nam" not in p["co"]) + "".join(HEAD_RE.match(t).group(1) + p_["van_ban_viet"] for p_, (_, _, t, _) in
                      ((q, h) for q, h in zip([p for p in pairs if "tieu_de_nam" in p["co"]], heads))))
    vi_orig = ws("".join(t for _, t in vp))
    skipped_vi = ws("".join(r["van_ban"] for r in unal if r["nguon"] == "viet"))
    ok_vi = sorted(vi_rebuilt + skipped_vi) == sorted(vi_orig)
    out = ROOT / "workspace" / "pkg" / label
    write_tsv(out / "pairs_draft.tsv", PAIR_COLS, pairs)
    write_tsv(out / "khong_dong.tsv", ["nguon", "dong", "ly_do", "van_ban"], unal)
    fl = Counter(f for p in pairs for f in p["co"].split(",") if f)
    rep = [f"{label} (NHAN TAM, chua co ma sach that): han {len(hp)} dong ({sum(len(t) for _, t in hp)} chu), viet {len(vp)} dong",
           f"tieu de nam chi co o ban Viet (dong 'NN年Nam ...'): {len(heads)}",
           f"khoi doan (Han doan, Viet doan): {dict(n_blocks)}; doan khong dong: {len(unal)}",
           f"doan co so cau Han = so cau Viet: {para_stats['cau_bang_nhau']}; khac: {para_stats['cau_lech']}",
           f"cap: {len(pairs)} (cap co Han: {sum(1 for p in pairs if p['van_ban_han'])}); co: {dict(fl)}",
           f"noi lai Han == file goc (da sap xep ky tu, tru tieu de nam): {ok_han}; noi lai Viet == file goc (bo khoang trang): {ok_vi}",
           "doan lech so cau (doan, dong Han, dong Viet, cau Han, cau Viet): " + "; ".join(map(str, odd))]
    (out / "report.txt").write_text("\n".join(rep) + "\n", encoding="utf-8")
    # ---- review tool: only pairs that are one contiguous slice of the Han stream
    rv = []
    for p in pairs:
        if "tieu_de_nam" in p["co"] or p["x"] < 0 or "han_khong_lien_tuc" in p["co"]:
            continue
        if p["van_ban_han"] != Hs[p["x"]:p["y"]]:
            continue
        rv.append({"id": str(p["stt"]), "doc": p["nhan_tam"], "vi": p["van_ban_viet"], "vr": p["van_ban_viet"], "s": p["x"], "e": p["y"],
                   "co": p["co"], "pv": str(p["trang_viet"]), "sug": None, "vs": [], "hs": []})
    rv.sort(key=lambda r: r["s"])
    tpl = (ROOT / "tools" / "review_tpl.html").read_text(encoding="utf-8")
    core = (ROOT / "tools" / "review_core.js").read_text(encoding="utf-8")
    data = json.dumps({"book": label, "H": Hs, "pages": [[0, 1]], "pairs": rv, "defaults": {"viet": False, "han": False}}, ensure_ascii=False).replace("</", "<\\/")
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / f"{label}_review.html").write_text(tpl.replace("__BOOK__", label).replace("/*CORE*/", core).replace("__DATA__", data), encoding="utf-8")
    rep.append(f"cap dua vao cong cu ra: {len(rv)}/{len(pairs)} (bo: tieu de nam tu dong Viet, cap Han khong lien tuc trong chuoi)")
    (out / "report.txt").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep[:-1][:6] + [rep[-1]]))
    return ok_han and ok_vi


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=["122", "123", "124"])
    a = ap.parse_args(argv)
    syl2c, c2syl = D.load_dictionary(glob.glob(str(ROOT / "docs-local" / "NLP-*" / "NLP" / "guideline" / "dict" / "QuocNgu_SinoNom_TongHop3.xlsx"))[0])

    def scorer_for(hp):
        return D.Scorer(syl2c, c2syl, Counter(c for _, t in hp for c in t), 0.72)

    ok = all([run(n, scorer_for, ROOT / "workspace" / "review") for n in a.only])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
