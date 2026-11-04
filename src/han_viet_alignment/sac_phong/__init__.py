"""Xử lý đặc thù R1001/R1003: Hán, phiên âm, dịch nghĩa; bắc cầu qua phiên âm."""

from .pdf_extractor import extract_page_images
from .layout_parser import process_and_crop_page
from .ocr_pipeline import process_viet_ocr, process_han_ocr
from .han_auto_corrector import get_corrector, syl_key, HanAutoCorrector
from .dictionary_helper import SinoNomDictionary

__all__ = [
    "extract_page_images",
    "process_and_crop_page",
    "process_viet_ocr",
    "process_han_ocr",
    "get_corrector",
    "syl_key",
    "HanAutoCorrector",
    "SinoNomDictionary",
]
