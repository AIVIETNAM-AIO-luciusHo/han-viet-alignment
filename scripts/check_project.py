"""Kiểm tra cấu hình dự án độc lập với công cụ AI; không chạy OCR hay truy cập dữ liệu local."""
import json
from pathlib import Path
import tomllib
import yaml

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    books = json.loads((root / "metadata/books.json").read_text(encoding="utf-8"))
    ids = [b["book_id"] for b in books]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Danh mục rỗng hoặc book_id trùng")
    for book in books:
        path = root / "configs/books" / (book["book_id"] + ".yaml")
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        for key in ("book_id", "has_phien_am", "source_path", "scope_status"):
            if config.get(key) != book[key]:
                raise ValueError(f"{path}: {key} khác danh mục")
        source = Path(book["source_path"])
        if source.is_absolute() or ".." in source.parts:
            raise ValueError("source_path phải tương đối trong source root")
        family_path = Path(config["family_config"])
        if family_path.is_absolute() or ".." in family_path.parts:
            raise ValueError("family_config không hợp lệ")
        family = yaml.safe_load((root / family_path).read_text(encoding="utf-8"))
        for key in ("has_phien_am", "han_input", "viet_input"):
            if family[key] != book[key]:
                raise ValueError(f"{book['book_id']}: {key} khác family")
        if book["book_id"] not in family["books"]:
            raise ValueError("Family thiếu mã sách")
    config_ids = {p.stem for p in (root / "configs/books").glob("*.yaml")}
    if config_ids != set(ids):
        raise ValueError("Cấu hình sách khác danh mục")
    package = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    if package["tool"]["setuptools"]["packages"]["find"]["where"] != ["src"]:
        raise ValueError("Package phải nằm trong src")
    return len(books)


if __name__ == "__main__":
    print(f"Cấu hình {check()} sách và package: OK")
