# Yêu cầu và căn cứ
Nguồn nằm trong `docs-local/NLP-20261101T150232Z-1-001/NLP/`:

| Nguồn | Vai trò |
| --- | --- |
| guideline/HUONG_DAN_DO_AN_HAN_VIET_HANH_CHINH.pdf | Mục 1–3: phạm vi, bàn giao, schema; mục 4: quy trình; mục 6–8: chất lượng; mục 9: báo cáo/mã nguồn |
| guideline/Quy_định_đồ_án.pdf | Quy định chung; phần định dạng bàn giao và đánh giá được tài liệu hành chính thay thế |
| DANH_SACH_SACH.xlsx, DANH_SACH và QUY_TAC_ID | Mã sách, thành phần, ID; Minh Mệnh không phiên âm và thuộc loại cần OCR |
| guideline/mau_du_lieu/MAU_parallel.tsv và .xlsx | Ví dụ 22 cặp, không phải dữ liệu đã làm của nhóm |
| guideline/mau_du_lieu/kiem_tra_du_lieu.py | Công cụ tham chiếu định dạng và khớp âm, không thay kiểm tra ngữ nghĩa |
| guideline/dict/QuocNgu_SinoNom_TongHop3.xlsx | Từ điển đánh giá chính thức; các từ điển còn lại hỗ trợ |

Đọc hai hướng dẫn trước khi triển khai. Không OCR hàng loạt trước khi xác nhận phạm vi
Hán/Việt tương ứng. Làm toàn bộ sách/phần được giao, kể cả trang có quan hệ dịch cần thu thập.
Nếu >20% trang chất lượng kém, liên hệ người giao sách.

Cả năm tập cần OCR phần Hán: tối thiểu 2.000 cặp hợp lệ/người, 8.000/nhóm bốn người,
tính tổng các sách được giao. Không áp chỉ tiêu 12.000 chỉ vì Minh Mệnh có lớp text Việt.
Dòng có □ hoặc [...] không tính chỉ tiêu. Cần đánh giá quan hệ dịch, không chỉ đếm dòng.

Tỷ lệ lỗi = số cặp lỗi / số cặp được kiểm tra hợp lệ, phải ≤30%, mục tiêu nội bộ ≤20%.
Sửa mọi lỗi phát hiện và rà soát tương tự trên toàn file. Với sách có phiên âm,
khớp âm từng chữ ≥95%; chữ ngoài từ điển và toàn bộ chữ của dòng lệch số chữ/âm tiết
đều tính không khớp; không tính □, không phân biệt vị trí dấu thanh hòa/hoà.
Minh Mệnh không có phiên âm: ghi chỉ số này là không áp dụng, không báo 100%.

Báo cáo cần họ tên/MSSV/email, phân công tới văn bản và số cặp, nguồn/công cụ/mô hình/prompt,
thống kê, khớp âm, tự kiểm tra và ảnh XLSX mở được không lỗi font.
source.zip cần README, USER_GUIDE, thư viện cố định phiên bản; không kèm bí mật.
Hai giáo trình AI trong docs-local là tài liệu tham khảo, không thay các quy định đồ án.
