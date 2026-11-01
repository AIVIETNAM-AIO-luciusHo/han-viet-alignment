# Metadata
`books.json` ghi mã sách và đường dẫn thực tế, đối chiếu DANH_SACH_SACH.xlsx.
Tên file tập 1/3 hiện khác cột File trong danh sách: giữ nguyên file gốc và lưu cả hai tên;
đối chiếu nội dung khi kiểm kê, không tự đổi mã sách.
`team.json` ghi thông tin đã cung cấp; null/chưa xác nhận không phải dữ liệu nộp hoàn chỉnh.

Các TSV hiện chỉ có header, chưa có văn bản được kiểm kê:
- documents: một dòng/văn bản; sequence là thứ tự sách, owner/reviewer dùng GitHub đã xác nhận.
- source_regions: một dòng/vùng nguồn; component là han/phien_am/dich_nghia;
  pdf_page đánh từ 1, folio giữ mốc tờ a/b; bbox_json là bốn điểm theo pixel ảnh render.
  Cần ghi kích thước ảnh/DPI và biến đổi trong manifest chạy trước khi tạo vùng thực tế.
- corrections: thay đổi text sạch; liên kết source_region_ids bằng danh sách JSON;
  không sửa OCR thô. timestamp dùng ISO 8601 có múi giờ.
- assignments: theo dõi số cặp hợp lệ theo người và văn bản, tránh đếm trùng giữa thành viên.
- quality_reviews: error_types là danh sách JSON gồm OMISSION/ADDITION/MISSING;
  ghi mẫu kiểm tra, sửa lỗi và rà soát lỗi tương tự trên toàn sách.

Các bảng nội bộ này không thêm cột vào TSV bàn giao. ID văn bản chỉ gán sau kiểm kê;
không đổi ID tùy tiện sau hiệu đính. Header-only không chứng minh sách đã xử lý.
