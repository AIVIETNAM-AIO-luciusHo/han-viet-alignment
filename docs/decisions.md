# Quyết định
Ngày 2026-11-01, theo khảo sát của leader:
- Phạm vi hiện tại: dựng khung repo, tài liệu, hợp đồng dữ liệu; chưa triển khai pipeline.
- Bốn thành viên; thông tin đã biết trong metadata/team.json.
- Ưu tiên tài nguyên laptop/GPU và công cụ miễn phí; engine chưa chọn.
- Chưa quyết định dịch vụ ngoài; mặc định tắt, chưa tải ảnh hoặc gọi API.
- Code dùng src/han_viet_alignment, logic chung độc lập hai nhóm sách.
- Dữ liệu lớn/OCR/ảnh/kết quả chạy nằm local; metadata nhỏ và tài liệu quy ước được commit.
- Chỉ metadata mẫu và cấu hình dự kiến; chưa có cơ chế kế thừa YAML hoặc runner.

Cần bổ sung sau: hạn nộp; MSSV/email; phân công từng doc_id; GPU/VRAM/RAM/OS; OCR backend và quyền dùng dịch vụ.
Leader cung cấp handle @AIVIETNAM-AIO-luciusHo cho CODEOWNERS; chưa kiểm chứng loại tài khoản/quyền trên GitHub.
Đã chốt A: ahihitoanne/TrongKiennn, B: vmq-16/leader.
Leader là owner duy nhất toàn repo; xem docs/governance.md cho chính sách PR và ngoại lệ PR của leader.

Trước khi triển khai: kiểm kê nguồn và thử vài văn bản đại diện cả hai nhóm sách,
đo tốc độ/VRAM/độ chính xác, rồi cố định dependency và phiên bản model.
Nếu đề xuất phương pháp mới: ghi lý do, input/output, kiểm chứng, rủi ro/dự phòng và tái lập.

## Đợt chuẩn bị F01 — 2026-11-01
CONFIRMED: cập nhật họ tên theo leader; giữ package hiện tại; chỉ viết tài liệu đặc tả.
CONFIRMED: leader yêu cầu sửa CODEOWNERS để phụ trách toàn repo; file local dùng một rule *.
PROPOSED: constitution draft và F01 tại .specify/memory/ và specs/001-shared-data-contract/.
NEEDS_CONFIRMATION: các quyết định NC01–NC08 trong F01; chưa phê chuẩn thiết kế trung gian.
Chưa cài/khởi tạo Spec Kit integration, viết pipeline, push, merge hoặc thay rulesets.

## Đồng bộ cây thư mục — 2026-11-01
CONFIRMED: đường dẫn package, config và CODEOWNERS hiện khớp nhau;
README được bổ sung cây thư mục thực tế, gồm .specify/ và specs/.
Giữ tên repository có dấu gạch nối và package Python dùng dấu gạch dưới.
Không đổi tên/di chuyển package, nguồn NLP hoặc tạo runner chưa triển khai.
Các thư mục test giữ tên theo chức năng; chỉ mở rộng khi triển khai feature liên quan.


## Cập nhật tooling — 2026-11-02
Spec Kit 1.2.5/Codex skills đã tích hợp, constitution và F01 vẫn draft.
CI thêm kiểm tra config và test cấu hình. Cách chạy cho thành viên nằm trong USER_GUIDE.md.
Các ghi chú chưa cài công cụ bên trên mô tả thời điểm soạn ban đầu.

CONFIRMED — 2026-11-02: GitHub xác nhận leader là User có admin; main đã có branch protection
(PR, 1 approval/owner, stale dismissal, resolved conversations, required scaffold,
force push/deletion tắt; admin được ngoại lệ). Không push/merge tự động.
NEEDS_CONFIRMATION: phê chuẩn constitution/F01 vẫn còn mở; công cụ đã sẵn sàng không thay phê chuẩn.

## CI độc lập công cụ AI — 2026-11-02
CONFIRMED: theo yêu cầu leader, check_project chỉ kiểm tra cấu hình/package.
Spec Kit/integration chuyển sang check_tooling.py tùy chọn và tests/tooling riêng.
Không cần Codex, Spec Kit CLI hoặc thư mục agent để chạy required check scaffold.
Không thay CODEOWNERS, workflow required status hoặc branch protection trong thay đổi này.

## Công cụ cá nhân của leader — 2026-11-02
CONFIRMED: leader dùng Claude; tooling.md là ghi chú dành cho leader, không yêu cầu thành viên cài agent.
Integration đã cài vẫn là codex; chưa chuyển sang Claude. Thành viên xem USER_GUIDE để chạy CI local.
GitHub xác định merge conflict; CI kiểm tra cấu hình/test, không bảo đảm mọi xung đột ngữ nghĩa.
Không thay workflow, CODEOWNERS hoặc quản trị GitHub ở đợt chỉnh tài liệu này.

CONFIRMED — 2026-11-02: docs/tooling.md là ghi chú local đã ignore, không thuộc bộ tài liệu chia sẻ; các liên kết bắt buộc tới file này đã bỏ.
