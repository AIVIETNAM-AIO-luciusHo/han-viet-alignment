"""Kiểm tra tính nhất quán khung, không kiểm định dữ liệu dóng hàng."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"R1001": 178, "R1003": 252, "R1204": 516, "R1205": 566, "R1206": 736}


def main():
    books = json.loads((ROOT / "metadata/books.json").read_text(encoding="utf-8"))
    if len(books) != len(EXPECTED) or {b["book_id"]: b["pdf_pages"] for b in books} != EXPECTED:
        raise ValueError("Danh mục mã sách/số trang không đúng nguồn được giao")
    for book in books:
        code = book["book_id"]
        if book["has_phien_am"] != (code in {"R1001", "R1003"}):
            raise ValueError(f"Sai khai báo phiên âm: {code}")
        if book["quota_class"] != "requires_ocr":
            raise ValueError(f"Sai loại chỉ tiêu: {code}")
        if not (ROOT / f"configs/books/{code}.yaml").is_file():
            raise ValueError(f"Thiếu cấu hình: {code}")
    for path in (ROOT / "src").rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    print("Khung hợp lệ: 5 mã sách, thành phần phiên âm, loại chỉ tiêu và cú pháp package.")
    print("Chưa kiểm tra dữ liệu nguồn, OCR, dóng hàng hoặc tiêu chí nghiệm thu.")


if __name__ == "__main__":
    main()
