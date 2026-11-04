"""
pdf_extractor.py — Module trích xuất ảnh chất lượng gốc từ file PDF scan.
Tận dụng luồng JPEG DCTDecode nhúng sẵn trong PDF để đạt tốc độ cao và giữ nguyên 100% độ phân giải scan gốc (3312x2336).
"""
import os
from pathlib import Path
import pypdf

def extract_page_images(pdf_path: str, output_dir: str, start_page: int = 1, end_page: int = None) -> list:
    """
    Trích xuất ảnh của các trang PDF từ start_page đến end_page (1-indexed).
    Trả về danh sách dict: [{'page_num': int, 'image_path': str, 'width': int, 'height': int}]
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file PDF: {pdf_path}")
        
    reader = pypdf.PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    
    if end_page is None or end_page > total_pages:
        end_page = total_pages
        
    extracted = []
    print(f"[*] Bắt đầu trích xuất ảnh từ {pdf_path.name} (trang {start_page} đến {end_page})...")
    
    for page_idx in range(start_page - 1, end_page):
        page_num = page_idx + 1
        page = reader.pages[page_idx]
        
        # Kiểm tra XObject trong resources
        if "/Resources" in page and "/XObject" in page["/Resources"]:
            xobjects = page["/Resources"]["/XObject"].get_object()
            img_found = False
            for obj_name in xobjects.keys():
                obj = xobjects[obj_name]
                if obj.get("/Subtype") == "/Image":
                    # Lấy kích thước
                    width = int(obj.get("/Width", 0))
                    height = int(obj.get("/Height", 0))
                    
                    # Tên file ảnh theo chuẩn số trang 3 chữ số
                    img_name = f"page_{page_num:03d}.jpg"
                    img_path = output_dir / img_name
                    
                    # Trích xuất dữ liệu ảnh
                    raw_data = obj.get_data()
                    with open(img_path, "wb") as f:
                        f.write(raw_data)
                        
                    extracted.append({
                        "page_num": page_num,
                        "image_path": str(img_path),
                        "width": width,
                        "height": height
                    })
                    img_found = True
                    break # Mỗi trang sách scan thường chỉ có 1 ảnh nền chính
            
            if not img_found:
                print(f"[!] Cảnh báo: Trang {page_num} không tìm thấy đối tượng Image.")
        else:
            print(f"[!] Cảnh báo: Trang {page_num} không chứa tài nguyên XObject.")
            
    print(f"[✓] Đã trích xuất {len(extracted)} trang ảnh vào {output_dir}")
    return extracted

if __name__ == "__main__":
    import sys
    pdf = sys.argv[1] if len(sys.argv) > 1 else "tap 1.pdf"
    out = sys.argv[2] if len(sys.argv) > 2 else "temp_pages"
    extract_page_images(pdf, out, 5, 8)

