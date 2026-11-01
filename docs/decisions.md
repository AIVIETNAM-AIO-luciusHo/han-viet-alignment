# Quyết định
Ngày 2026-11-01, theo khảo sát của leader:
- Phạm vi hiện tại: dựng khung repo, tài liệu, hợp đồng dữ liệu; chưa triển khai pipeline.
- Bốn thành viên; thông tin đã biết trong metadata/team.json.
- Ưu tiên tài nguyên laptop/GPU và công cụ miễn phí; engine chưa chọn.
- Chưa quyết định dịch vụ ngoài; mặc định tắt, chưa tải ảnh hoặc gọi API.
- Code dùng src/han_viet_alignment, logic chung độc lập hai nhóm sách.
- Dữ liệu lớn/OCR/ảnh/kết quả chạy nằm local; metadata nhỏ và tài liệu quy ước được commit.
- Chỉ metadata mẫu và cấu hình dự kiến; chưa có cơ chế kế thừa YAML hoặc runner.

Cần bổ sung sau: hạn nộp; họ tên đầy đủ/MSSV/email; phân công từng doc_id; GPU/VRAM/RAM/OS; OCR backend và quyền dùng dịch vụ.
Leader cung cấp handle @AIVIETNAM-AIO-luciusHo cho CODEOWNERS; chưa kiểm chứng loại tài khoản/quyền trên GitHub.
Đã chốt A: ahihitoanne/TrongKiennn, B: vmq-16/leader.
Leader là owner duy nhất toàn repo; xem docs/governance.md cho chính sách PR và ngoại lệ PR của leader.

Trước khi triển khai: kiểm kê nguồn và thử vài văn bản đại diện cả hai nhóm sách,
đo tốc độ/VRAM/độ chính xác, rồi cố định dependency và phiên bản model.
Nếu đề xuất phương pháp mới: ghi lý do, input/output, kiểm chứng, rủi ro/dự phòng và tái lập.
