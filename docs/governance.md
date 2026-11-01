# Phân công và review

## Trách nhiệm
Leader @AIVIETNAM-AIO-luciusHo là CODEOWNER duy nhất cho toàn repo, gồm cả
.github/CODEOWNERS, cấu hình, mã nguồn, kiểm thử, metadata và tài liệu.
Team A (@ahihitoanne, @TrongKiennn) phụ trách sắc phong R1001/R1003.
Team B (@vmq-16, leader) phụ trách Minh Mệnh R1204/R1205/R1206.
Phân công chuyên môn không cấp quyền duyệt thay leader trong CODEOWNERS.
Thành viên phụ trách phát triển và review chéo; leader kiểm tra tích hợp và quyết định merge.

## Quy trình pull request
1. Tạo nhánh làm việc từ main; nêu phạm vi và mã sách/doc_id trong PR.
2. Mời người phụ trách chuyên môn review, xử lý nhận xét và chạy kiểm tra phù hợp.
3. Leader review trước khi merge; khi có commit mới, cần review lại phần thay đổi.
4. Sửa dữ liệu phải có nguồn đối chiếu và bản ghi hiệu đính; không sửa OCR thô.

## Cấu hình trên GitHub
Các mục dưới đây là hướng dẫn; chưa được áp dụng trên GitHub bởi việc sửa repo local.
Trước khi bật, xác minh handle leader là tài khoản người dùng có quyền write;
nếu là tổ chức, thay bằng username cá nhân hoặc team hợp lệ dạng @org/team.
Đảm bảo CODEOWNERS đã có trong nhánh đích của PR và GitHub không báo lỗi owner.

Trong Settings → Rules → Rulesets hoặc Branches, bảo vệ main:
- Require a pull request before merging.
- Require ít nhất 1 approval và Require review from Code Owners.
- Dismiss stale pull request approvals when new commits are pushed.
- Require status checks to pass: chọn check scaffold sau khi workflow đã chạy.
- Chặn force push và xóa nhánh main; giải quyết các cuộc thảo luận trước merge.
- Giới hạn khả năng bypass theo chính sách PR leader bên dưới; không cấp bypass cho cả nhóm.

CODEOWNERS chỉ định reviewer, không tự bật bảo vệ nhánh hoặc thay đổi quyền repository.
Nhiều owner trên một dòng cho phép một người trong số đó duyệt, không bắt buộc tất cả.
Quy tắc khớp cuối cùng thay thế quy tắc trước; giữ duy nhất dòng * để leader luôn là owner.

## PR do leader tạo
Leader không thể tự approve PR của mình. Với leader là owner duy nhất và bắt buộc
owner review, PR của leader cần ngoại lệ quản trị để tránh bế tắc.
Đề xuất: leader tạo PR, mời ít nhất một thành viên khác review, đợi CI đạt và ghi
lý do bypass owner approval trong PR trước khi dùng quyền bypass giới hạn cho leader.
Cấu hình bypass tùy quyền/gói GitHub; không tắt bảo vệ cho toàn nhóm chỉ để merge một PR.
Nếu không muốn cho phép bypass, cần thiết kế lại owner/ruleset và chấp nhận mô hình
phê duyệt khác; file CODEOWNERS hiện tại chưa giải quyết trường hợp đó tự động.

## Tài liệu GitHub
- [CODEOWNERS: thứ tự quy tắc, quyền và approval](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- [Bảo vệ nhánh](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
