# Constitution — han-viet-alignment

Version: 0.1.0-draft | Ngày soạn: 2026-11-01
Trạng thái: PROPOSED — chưa phê chuẩn. Không tuyên bố đã cài đặt Spec Kit CLI/integration.
Đây là bản dự thảo tại đường dẫn dự kiến của Spec Kit, không phải scaffold được khởi tạo lại.

## Căn cứ và trạng thái
CONFIRMED là yêu cầu có trong quy định gốc hoặc được leader cung cấp.
PROPOSED là thiết kế nội bộ cần review. NEEDS_CONFIRMATION là quyết định còn mở,
phải ghi người có thẩm quyền và tác động; không biến thành giả định ngầm.
Tài liệu gốc trong docs-local/NLP-20261101T150232Z-1-001/NLP:
- guideline/HUONG_DAN_DO_AN_HAN_VIET_HANH_CHINH.pdf, mục 1–9.
- guideline/Quy_định_đồ_án.pdf: quy định chung; tài liệu hành chính thay phần bàn giao/đánh giá.
- DANH_SACH_SACH.xlsx: DANH_SACH, QUY_TAC_ID; mẫu và script trong guideline/mau_du_lieu.
Khi tài liệu repo lệch nguồn, ghi xung đột và sửa theo nguồn có thẩm quyền, không âm thầm đổi yêu cầu.

## I. Trung thành với nguồn — CONFIRMED
Giữ PDF gốc; OCR thô bất biến, text sạch và dóng hàng tách riêng.
Không dùng LLM/công cụ dịch để dịch bù, thay bản dịch, sửa văn phong.
Giữ chữ Hán/phồn/dị thể, tên riêng và niên hiệu theo nguồn; không tự chuyển giản/phồn.
Sửa OCR và phiên âm phải có đối chiếu nguồn và lý do. Dùng □ và [...] theo hướng dẫn,
không suy đoán lấp chỗ khuyết. Ảnh thay đổi phải có PDF updated và báo cáo tương ứng.

## II. Một kiến trúc, một hợp đồng — CONFIRMED
Giữ src/han_viet_alignment/; thay kiến trúc cần lý do kỹ thuật và leader phê duyệt.
Hai team dùng chung ID, schema đầu ra và quy tắc kiểm định; không tạo schema bàn giao riêng.
Không hard-code mã sách, tên người, đường dẫn máy hoặc OCR backend trong logic runtime.
Mã và thuộc tính sách lấy từ danh mục đối chiếu chính thức; danh sách cụ thể được phép ở metadata/config.
Không dựng lại scaffold, xóa/đổi tên/ghi đè file hiện có khi không cần thiết.
Hợp đồng trung gian F01 là PROPOSED, chỉ trở thành chuẩn sau review.

## III. Truy vết và tái lập — CONFIRMED; cơ chế PROPOSED
Mọi kết quả liên kết tới doc_id và nguồn có sẵn. Không bịa trang hoặc tọa độ khi chưa biết.
Kết quả chưa đủ truy vết phải nêu thiếu gì; chưa được coi là sẵn sàng bàn giao.
Đề xuất lưu phiên bản schema, config đã resolve, hash nguồn, model/version/prompt nếu dùng,
thiết bị, thời gian chạy và chuỗi liên kết cặp→đoạn sạch→OCR/trích text→vùng/trang.
Dependency sử dụng thực tế phải cố định phiên bản; không tuyên bố tái lập chỉ dựa vào README.

## IV. Chất lượng và độ phủ — CONFIRMED
TSV đúng bảy cột; UTF-8 không BOM/NFC/LF; XLSX một sheet DONG_HANG giống TSV,
không công thức/gộp ô. ID theo thứ tự sách và câu trong văn bản.
Tỷ lệ lỗi ≤30%, mục tiêu nội bộ ≤20%; mọi lỗi phát hiện phải sửa và rà soát tương tự.
Sách có phiên âm cần khớp âm ≥95% theo QuocNgu_SinoNom_TongHop3.xlsx;
chữ ngoài từ điển và chữ trong dòng lệch số chữ/âm tiết tính không khớp, loại □ khỏi mẫu số.
Không có phiên âm: ghi không áp dụng, không sinh phiên âm để đạt điểm.
Dòng có □/[...] không tính chỉ tiêu; không dùng số dòng không khuyết thay chứng nhận ngữ nghĩa.
Cả năm sách cần OCR phần Hán: 2.000 cặp hợp lệ/người, 8.000/nhóm theo nguồn hiện có.
Phương án lấy mẫu nghiệm thu chi tiết: NEEDS_CONFIRMATION với giảng viên.

## V. Phát triển trên mẫu thật — CONFIRMED
Tuần 1: Team A thử R1001/R1003; Team B thử R1204/R1205/R1206.
Chưa OCR hàng loạt hoặc phân chia sản lượng cố định. Ưu tiên Python 3.11+, công cụ miễn phí,
GPU laptop khi có; đánh giá CPU khi khả thi. Chọn backend sau đo pilot, không hứa hiệu năng chưa đo.
Chưa triển khai phải ghi rõ chưa triển khai. Mỗi feature có tiêu chí nghiệm thu quan sát được;
kiểm tra hợp đồng không thay kiểm tra ngữ nghĩa bởi con người.

## VI. Quyền dữ liệu và quản trị — CONFIRMED
Không đưa PDF/từ điển lớn/nguồn hoặc bí mật lên GitHub khi chưa có quyền.
Không gửi ảnh tới dịch vụ ngoài khi chưa được phép; không gọi API ngầm.
Không tự merge/push/sửa rulesets hay quản trị repo. CODEOWNERS chỉ sửa khi leader yêu cầu rõ.
Leader là owner toàn repo; Team A/B chịu trách nhiệm chuyên môn theo metadata.
Quyền owner trên GitHub và chính sách PR leader cần kiểm chứng/cấu hình riêng.

## Quy trình và sửa đổi — PROPOSED
Trình tự: constitution draft → feature spec → clarify → plan → tasks → review → triển khai được cho phép.
Không chạy implement trong đợt chuẩn bị đặc tả này. Thay hợp đồng phải có impact analysis,
version/migration khi cần và review của hai team; leader phê chuẩn trước áp dụng.
Không cho config hoặc feature spec làm yếu quy định nguồn; ngoại lệ cần người có thẩm quyền xác nhận.
NEEDS_CONFIRMATION: leader phê chuẩn constitution, phiên bản Spec Kit/integration, chính sách migration.
