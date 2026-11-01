"""Kiểm tra tính nhất quán khung, không kiểm định dữ liệu dóng hàng."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    books = json.loads((ROOT / "metadata/books.json").read_text(encoding="utf-8"))
    ids = [b["book_id"] for b in books]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Danh mục rỗng hoặc book_id trùng")
    for book in books:
        code = book["book_id"]
        if type(book["pdf_pages"]) is not int or book["pdf_pages"] < 1:
            raise ValueError(f"Số trang không hợp lệ: {code}")
        if type(book["has_phien_am"]) is not bool:
            raise ValueError(f"Thuộc tính phiên âm không hợp lệ: {code}")
        if not (ROOT / f"configs/books/{code}.yaml").is_file():
            raise ValueError(f"Thiếu cấu hình: {code}")
    for path in (ROOT / "src").rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    print("Khung hợp lệ: danh mục, kiểu thuộc tính và cú pháp package.")
    print("Chưa kiểm tra dữ liệu nguồn, OCR, dóng hàng hoặc tiêu chí nghiệm thu.")


if __name__ == "__main__":
    main()
