# Hợp đồng dữ liệu
## ID và thứ tự
Mã sách duy nhất: R1001, R1003, R1204, R1205, R1206.
`doc_id = <MA_SACH>.<thứ tự văn bản ít nhất 3 chữ số>`, bắt đầu 001 theo sách.
`sent_id = <doc_id>.<thứ tự câu từ 1>`, duy nhất; giữ thứ tự sách.
Sắc phong: mỗi văn bản là một đơn vị; Minh Mệnh: mỗi điều chép/sự việc/chiếu dụ là một văn bản.

## TSV và XLSX bàn giao
Đúng bảy cột theo thứ tự:
`sent_id`, `doc_id`, `doc_type`, `han`, `phien_am`, `dich_nghia`, `ghi_chu`.
UTF-8 không BOM, NFC, LF, một cặp/một dòng vật lý, không dòng trống;
không tab/xuống dòng trong ô, không khoảng trắng thừa đầu/cuối.
XLSX chỉ một sheet DONG_HANG, cùng cột/nội dung/thứ tự với TSV, không công thức hoặc gộp ô.

| Cột | Quy tắc |
| --- | --- |
| sent_id, doc_id | Bắt buộc; theo quy tắc trên |
| doc_type | sac_phong, che_phong, chieu_phong, chau_ban, khac; để trống khi không xác định |
| han | Bắt buộc; viết liền, giữ phồn/dị thể và chữ số đại tự; chỉ chữ Hán, □, dấu câu Hán có trong nguồn |
| phien_am | Bắt buộc khi sách có; giữ hoa/thường và dấu câu; khớp từng chữ/âm tiết; Minh Mệnh để trống |
| dich_nghia | Bắt buộc; bản dịch sách, giữ con số/năm; bỏ chỉ mục và chú thích chân trang; chỉ sửa OCR |
| ghi_chu | Giải thích khuyết chữ và sửa so với nguồn |

Không tự chuyển giản/phồn; OCR giản thể sai phải sửa theo ảnh gốc.
Không dùng LLM/công cụ dịch để dịch bù, viết lại, sửa văn phong bản dịch.
Phiên âm sai phải sửa theo chữ Hán và ghi chú. Chữ khuyết dùng mỗi chữ một □ ở Hán
và phiên âm nếu có; dịch khuyết dùng [...], ghi lý do. Không suy đoán để lấp dữ liệu thiếu.

Chấp nhận 1–1, 1–n, n–1; n–m khi không thể tách hợp lý. Ưu tiên đơn vị nhỏ nhất đủ nghĩa,
không chia máy móc theo dấu câu, không gộp cả văn bản thành một dòng.

## Nguồn, OCR và text sạch
Ảnh mỗi văn bản: `<doc_id>_<k>.jpg`, k từ 1. Trang nhiều văn bản cần ảnh riêng cho từng văn bản.
OCR thô: han/<doc_id>.txt và viet/<doc_id>.txt, không sửa tay.
Nếu có box, Label.txt là đường dẫn tương đối + TAB + mảng JSON, mỗi box có transcription
và points đúng 4 điểm. Hán dọc theo cột phải→trái, trên→dưới; Việt trên→dưới.
Text sạch tách han.txt, phien_am.txt, dich_nghia.txt; mỗi văn bản mở đầu `### <doc_id>`.
Minh Mệnh giữ phien_am.txt theo cấu trúc bàn giao, không sinh nội dung phiên âm.
Giữ PDF gốc nguyên vẹn; sửa ảnh phải có `<MA_SACH>_updated.pdf` và báo cáo thay đổi.

## Cấu trúc gói nộp
```text
<MSSV1_MSSV2_MSSV3_MSSV4>.zip
├── <MA_SACH>/
│   ├── 01_nguon/                 # PDF gốc và updated nếu có
│   ├── 02_ocr_tho/
│   │   ├── han/                  # Ảnh, OCR theo doc_id; Label.txt nếu có box
│   │   └── viet/
│   ├── 03_text_sach/
│   │   ├── han.txt
│   │   ├── phien_am.txt
│   │   └── dich_nghia.txt
│   └── 04_dong_hang/
│       ├── <MA_SACH>_parallel.tsv
│       └── <MA_SACH>_parallel.xlsx
├── <MSSV1_MSSV2_MSSV3_MSSV4>_report.pdf
└── source.zip
```
Không dùng cây repo phát triển thay cây bàn giao. Chỉ tạo gói sau khi kiểm tra đầy đủ
nguồn, độ phủ, hiệu đính, chất lượng và thông tin thành viên.

## Thiết kế trung gian đang review
[Contract F01](../specs/001-shared-data-contract/contracts/intermediate.md) là PROPOSED,
chưa thay đổi định dạng bàn giao hoặc các bảng metadata hiện có. Việc biểu diễn
phien_am.txt khi sách không có phiên âm là NEEDS_CONFIRMATION với người giao sách.
