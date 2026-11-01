# Hướng dẫn trên máy mới
## Phạm vi hiện tại
Repo mới có khung package, metadata và hợp đồng. Chưa có lệnh OCR/dóng hàng/xuất gói;
không thể chạy từ đầu tới sản phẩm nộp ở giai đoạn này.

## Kiểm tra khung
Cần Python 3.11 trở lên. Từ thư mục gốc:
```sh
python3 scripts/check_scaffold.py
```
Lệnh dùng thư viện chuẩn, kiểm tra mã sách, số trang khai báo và cú pháp package;
không đọc nội dung sách, không kiểm định chất lượng dữ liệu.
Nếu đã có pip và muốn cài package trong môi trường riêng:
```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```
Build backend được cố định trong pyproject.toml; chưa có dependency OCR/runtime.
Cài đặt cần mạng hoặc cache setuptools tương ứng. Không cần cài package để kiểm tra khung.

## Chuẩn bị dữ liệu
Đặt bộ NLP được giao trong docs-local theo đường dẫn metadata/books.json;
không commit PDF, từ điển hoặc ảnh. Nếu bố cục local khác, cập nhật đường dẫn metadata
và configs/books tương ứng. Giữ PDF gốc, đối chiếu tên và phạm vi trước khi xử lý.
Thông tin chưa biết trong metadata/team.json cần xác nhận trước khi báo cáo.

## Quy trình sẽ triển khai
1. Xác nhận phạm vi và lập documents/source_regions, gán doc_id theo sách.
2. Thử trích text Việt Minh Mệnh và OCR mẫu; chọn backend sau khi đo GPU.
3. Lưu OCR thô, làm sạch riêng, ghép phần bị ngắt trang, hiệu đính có nguồn.
4. Dóng hàng theo từng nhóm sách; Minh Mệnh không tạo phiên âm.
5. Kiểm tra schema/độ phủ/khớp âm và đánh giá ngữ nghĩa bởi người.
6. Xuất TSV/XLSX, báo cáo và source.zip theo docs/contract.md.

Script gốc guideline/mau_du_lieu/kiem_tra_du_lieu.py cần pandas và openpyxl;
chưa đưa hai thư viện vào runtime vì chưa triển khai bước đó.
Khi tích hợp cần cố định phiên bản và bổ sung kiểm tra: mã/ID, phiên âm theo sách,
XLSX không công thức/gộp ô, độ phủ, ngưỡng chất lượng. Mã thoát 0 của script gốc
không tự xác nhận mọi tiêu chí nghiệm thu.

## Quy ước đường dẫn
[Cây thư mục trong README](README.md#cây-thư-mục-hiện-tại) mô tả repo thực tế.
Code thuộc src/han_viet_alignment/, không dùng src/sac_phong/ hoặc src/minh_menh/.
Tên thư mục tests/sac_phong/ và tests/minh_menh/ là đúng vì tests nhóm theo chức năng.
Không đổi tên tài liệu gốc trong docs-local để ép theo quy ước tên module.
workspace/ được tạo local khi cần; Git không lưu thư mục rỗng hoặc dữ liệu đã ignore.


## Kiểm tra trước khi mở PR
Không cần Claude, Codex hoặc Spec Kit CLI. Cần Python ≥3.11:
```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-ci.txt
.venv/bin/python scripts/check_scaffold.py
.venv/bin/python scripts/check_project.py
.venv/bin/python -m unittest discover -s tests/common -p 'test_*.py' -v
```
Windows dùng .venv/Scripts/python.exe.
Mở PR vào main, xem mục Checks và xử lý lỗi; nếu GitHub báo merge conflict,
cập nhật nhánh và giải quyết xung đột. Nhờ leader review trước khi merge.
CI hiện kiểm tra khung/cấu hình, chưa kiểm tra chất lượng pipeline OCR/dóng hàng.
Công cụ AI cá nhân của leader không phải yêu cầu cài đặt của thành viên.
