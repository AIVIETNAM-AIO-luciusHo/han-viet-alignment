"""Kiểm tra lỗi cấu hình trên bản sao; không cần PDF/GPU/mạng."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_project", ROOT / "scripts/check_project.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProjectConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("metadata", "configs"):
            shutil.copytree(ROOT / name, self.root / name)
        shutil.copy(ROOT / "pyproject.toml", self.root)

    def test_checkout_without_ai_tooling_or_local_sources(self):
        for name in (".agents", ".specify", ".codex", "docs-local"):
            self.assertFalse((self.root / name).exists())
        self.assertGreater(MODULE.check(self.root), 0)

    def mutate_catalog(self, change):
        path = self.root / "metadata/books.json"
        books = json.loads(path.read_text())
        change(books)
        path.write_text(json.dumps(books))
        with self.assertRaises(ValueError):
            MODULE.check(self.root)

    def test_duplicate_book(self):
        self.mutate_catalog(lambda books: books.append(books[0]))

    def test_config_conflict(self):
        self.mutate_catalog(lambda books: books[0].update(has_phien_am=not books[0]["has_phien_am"]))

    def test_missing_book_config(self):
        next((self.root / "configs/books").glob("*.yaml")).unlink()
        with self.assertRaises(FileNotFoundError):
            MODULE.check(self.root)


if __name__ == "__main__":
    unittest.main()
