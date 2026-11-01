# Kiểm thử
Có test cấu hình chung trong common/test_project_config.py; chưa có kiểm thử thuật toán vì pipeline chưa triển khai. Khi triển khai, dùng fixtures nhỏ,
kiểm tra ID sai, TSV lỗi encoding, thiếu phiên âm theo sách, XLSX khác TSV,
khuyết chữ, truy vết nguồn và việc loại dữ liệu thô khỏi sửa chữa.
Không dùng số cặp hay khớp âm thay cho đánh giá ngữ nghĩa.

CI bắt buộc chỉ chạy tests/common; bản sao test không chứa .agents/ hoặc .specify/.
Tooling tùy chọn có test riêng trong tests/tooling, không thuộc required check.
