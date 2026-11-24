"""Giao diện sửa chữ Hán trong file parallel bằng từ điển âm Hán-Việt + ảnh gốc.

Chạy:  python tools/fix_ui/server.py --book R1001  [--port 8765]
Rồi mở http://127.0.0.1:8765

- Cột 1: chữ Hán trong từ điển ứng với âm của ô đang chọn (ưu tiên chữ giống chữ OCR gốc, chữ hay gặp trong sách).
- Cột 2: các câu Hán của văn bản, mỗi chữ một ô; dưới mỗi ô là âm tiết phiên âm tương ứng.
- Cột 3: ảnh gốc có khung các dòng OCR (khung chứa chữ đang chọn được tô sáng).

Hai chế độ: (1) verify phiên âm + dịch nghĩa (sửa text, đánh dấu câu đã duyệt), (2) sửa chữ Hán.
Trạng thái duyệt lưu ở <book>/04_dong_hang/<book>_review.json.

Mỗi lần sửa, server ghi lại cột tương ứng của <book>/04_dong_hang/<book>_parallel.tsv (bản sao
gốc lưu một lần ở *.tsv.bak) và nối một dòng vào metadata/corrections.tsv.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from han_viet_alignment.common.text import MISSING, clean_cell, is_han, nfc, syl_key, syllables  # noqa: E402

DICT_DIR = ROOT / "guideline" / "dict"
HERE = Path(__file__).resolve().parent
CORR_FIELDS = ["change_id", "doc_id", "sent_id", "field", "before", "after", "reason",
               "source_region_ids", "editor", "reviewer", "timestamp"]
OCR_NOTE = re.compile(r"(\S)≠([^,;)\s]+)")


def load_dict():
    import pandas as pd

    df = pd.read_excel(DICT_DIR / "QuocNgu_SinoNom_TongHop3.xlsx", dtype=str).dropna()
    key2chars: dict[str, list[str]] = {}
    char2syls: dict[str, list[str]] = {}
    for qn, sn in zip(df.iloc[:, 0], df.iloc[:, 1]):
        qn = nfc(qn.strip().lower())
        k = syl_key(qn)
        lst = key2chars.setdefault(k, [])
        for ch in sn.strip():
            if ch not in lst:
                lst.append(ch)
            s = char2syls.setdefault(ch, [])
            if qn not in s:
                s.append(qn)
    similar: dict[str, list[str]] = {}
    sim_path = DICT_DIR / "SinoNom_Similar_Dic_v2.xlsx"
    if sim_path.exists():
        sdf = pd.read_excel(sim_path, dtype=str).dropna()
        for ch, lst in zip(sdf.iloc[:, 0], sdf.iloc[:, 1]):
            try:
                similar[ch.strip()] = list(ast.literal_eval(lst))
            except (ValueError, SyntaxError):
                pass
    return key2chars, char2syls, similar


class Book:
    MODES = ("pa_dn", "han")

    def __init__(self, book: str):
        self.book = book
        self.dir = ROOT / book
        self.tsv = self.dir / "04_dong_hang" / f"{book}_parallel.tsv"
        self.review_path = self.dir / "04_dong_hang" / f"{book}_review.json"
        self.lock = threading.Lock()
        with self.tsv.open(encoding="utf-8", newline="") as f:
            r = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
            self.fields = r.fieldnames
            self.rows = list(r)
        self.by_sent = {row["sent_id"]: row for row in self.rows}
        self.pages = {}
        pm = self.dir / "page_mapping.tsv"
        if pm.exists():
            with pm.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f, delimiter="\t"):
                    self.pages[row["doc_id"]] = row
        self.labels = {}
        for side in ("han", "viet"):
            label = self.dir / "02_ocr_tho" / side / "Label.txt"
            if not label.exists():
                continue
            for line in label.read_text(encoding="utf-8").splitlines():
                if "\t" in line:
                    img, js = line.split("\t", 1)
                    try:
                        self.labels[img.strip()] = json.loads(js)
                    except json.JSONDecodeError:
                        pass
        self.review = json.loads(self.review_path.read_text(encoding="utf-8")) if self.review_path.exists() else {}
        self.freq = Counter(ch for row in self.rows for ch in row["han"] if is_han(ch))

    def docs(self):
        out: dict[str, dict] = {}
        for row in self.rows:
            d = out.setdefault(row["doc_id"], {"doc_id": row["doc_id"], "sents": 0, "missing": 0,
                                               "done": {m: 0 for m in self.MODES}})
            d["sents"] += 1
            d["missing"] += row["han"].count(MISSING)
            for m in self.MODES:
                d["done"][m] += m in self.review.get(row["sent_id"], {})
        return list(out.values())

    def _sent(self, row):
        ocr_hints = [[m.group(1), m.group(2)] for m in OCR_NOTE.finditer(row.get("ghi_chu", ""))]
        return {"sent_id": row["sent_id"], "han": row["han"], "phien_am": row["phien_am"],
                "syls": syllables(row["phien_am"]), "dich_nghia": row["dich_nghia"],
                "ghi_chu": row.get("ghi_chu", ""), "ocr_hints": ocr_hints,
                "review": {m: True for m in self.review.get(row["sent_id"], {})}}

    def doc(self, doc_id: str):
        sents = [self._sent(row) for row in self.rows if row["doc_id"] == doc_id]
        page = self.pages.get(doc_id, {})
        han_img = page.get("han_image") or f"han/{doc_id}_1.jpg"
        viet_img = page.get("viet_image") or f"viet/{doc_id}_1.jpg"
        return {"doc_id": doc_id, "sents": sents, "page": page,
                "han_image": han_img, "viet_image": viet_img,
                "boxes": {"han": self.labels.get(han_img, []), "viet": self.labels.get(viet_img, [])}}

    def set_char(self, sent_id: str, idx: int, ch: str, editor: str):
        with self.lock:
            row = self.by_sent[sent_id]
            chars = list(row["han"])
            if not (0 <= idx < len(chars)):
                raise ValueError("idx ngoài phạm vi")
            chars[idx] = ch
            self._update(row, "han", "".join(chars), editor,
                         f"sửa chữ thứ {idx + 1} theo ảnh gốc + từ điển âm (fix_ui)")
            return self._sent(row)

    def insert_missing(self, sent_id: str, idx: int, n: int, editor: str):
        """Chèn n ô □ vào câu Hán tại vị trí idx (idx = len -> thêm cuối câu)."""
        if not (1 <= n <= 50):
            raise ValueError("số ô □ phải từ 1 đến 50")
        with self.lock:
            row = self.by_sent[sent_id]
            chars = list(row["han"])
            if not (0 <= idx <= len(chars)):
                raise ValueError("idx ngoài phạm vi")
            chars[idx:idx] = [MISSING] * n
            self._update(row, "han", "".join(chars), editor,
                         f"chèn {n} ô {MISSING} tại vị trí {idx + 1} cho khớp số âm phiên âm (fix_ui)")
            return self._sent(row)

    def set_field(self, sent_id: str, field: str, value: str, editor: str):
        if field not in ("phien_am", "dich_nghia"):
            raise ValueError("field không hợp lệ")
        with self.lock:
            row = self.by_sent[sent_id]
            self._update(row, field, clean_cell(value), editor, f"hiệu đính {field} theo ảnh gốc (fix_ui)")
            return self._sent(row)

    def set_review(self, sent_id: str, mode: str, done: bool, editor: str):
        if mode not in self.MODES or sent_id not in self.by_sent:
            raise ValueError("mode/sent_id không hợp lệ")
        with self.lock:
            r = self.review.setdefault(sent_id, {})
            if done:
                r[mode] = {"by": editor, "at": _now()}
            else:
                r.pop(mode, None)
                if not r:
                    self.review.pop(sent_id)
            tmp = self.review_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.review, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
            os.replace(tmp, self.review_path)
            return self._sent(self.by_sent[sent_id])

    def _update(self, row, field, after, editor, reason):
        before = row[field]
        if before == after:
            return
        row[field] = after
        bak = self.tsv.with_suffix(".tsv.bak")
        if not bak.exists():
            shutil.copy2(self.tsv, bak)
        tmp = self.tsv.with_suffix(".tsv.tmp")
        with tmp.open("w", encoding="utf-8", newline="") as f:
            f.write("\t".join(self.fields) + "\n")
            for r in self.rows:
                f.write("\t".join(r.get(k) or "" for k in self.fields) + "\n")
        os.replace(tmp, self.tsv)
        self._log(row, field, before, after, reason, editor)

    def _log(self, row, field, before, after, reason, editor):
        path = ROOT / "metadata" / "corrections.tsv"
        new = not path.exists() or path.stat().st_size == 0
        n = sum(1 for _ in path.open(encoding="utf-8")) if not new else 1
        with path.open("a", encoding="utf-8", newline="") as f:
            if new:
                f.write("\t".join(CORR_FIELDS) + "\n")
            vals = [f"C{n:05d}", row["doc_id"], row["sent_id"], field, before, after, reason, "[]", editor, "", _now()]
            f.write("\t".join(v.replace("\t", " ") for v in vals) + "\n")


def _now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def make_handler(book: Book, dic, editor: str):
    key2chars, char2syls, similar = dic

    def candidates(syl: str, ocr: str):
        chars = list(key2chars.get(syl_key(syl), [])) if syl else []
        sim = similar.get(ocr, []) if ocr else []
        sim_rank = {c: i for i, c in enumerate(sim)}
        order = {c: i for i, c in enumerate(chars)}
        chars.sort(key=lambda c: (c not in sim_rank, sim_rank.get(c, 0), -book.freq.get(c, 0), order[c]))
        return [{"ch": c, "freq": book.freq.get(c, 0), "similar": c in sim_rank,
                 "syls": char2syls.get(c, [])[:6]} for c in chars]

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if u.path in ("/", "/index.html"):
                return self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
            if u.path == "/api/info":
                return self._json({"book": book.book, "editor": editor, "docs": book.docs()})
            if u.path == "/api/doc":
                return self._json(book.doc(q.get("id", "")))
            if u.path == "/api/candidates":
                return self._json({"syl": q.get("syl", ""), "items": candidates(q.get("syl", ""), q.get("ocr", ""))})
            if u.path == "/api/char":
                ch = q.get("ch", "")
                return self._json({"ch": ch, "syls": char2syls.get(ch, []), "similar": similar.get(ch, [])})
            if u.path.startswith("/img/"):
                rel = unquote(u.path[len("/img/"):])
                base = (book.dir / "02_ocr_tho").resolve()
                p = (base / rel).resolve()
                if base in p.parents and p.is_file():
                    return self._send(200, p.read_bytes(), "image/jpeg")
                return self._send(404, b"not found", "text/plain")
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            u = urlparse(self.path)
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            ed = body.get("editor") or editor
            try:
                if u.path == "/api/set":
                    return self._json({"ok": True, "sent": book.set_char(body["sent_id"], int(body["idx"]), body["ch"], ed)})
                if u.path == "/api/insert":
                    return self._json({"ok": True, "sent": book.insert_missing(body["sent_id"], int(body["idx"]), int(body.get("n", 1)), ed)})
                if u.path == "/api/set_field":
                    return self._json({"ok": True, "sent": book.set_field(body["sent_id"], body["field"], body["value"], ed)})
                if u.path == "/api/review":
                    return self._json({"ok": True, "sent": book.set_review(body["sent_id"], body["mode"], bool(body["done"]), ed)})
            except (KeyError, ValueError) as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            self._send(404, b"not found", "text/plain")

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="R1001")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    try:
        editor = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True,
                                cwd=ROOT).stdout.strip()
    except OSError:
        editor = ""
    book = Book(a.book)
    print("Đang nạp từ điển...", flush=True)
    dic = load_dict()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(book, dic, editor))
    print(f"{a.book}: {len(book.rows)} câu. Mở http://127.0.0.1:{a.port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
