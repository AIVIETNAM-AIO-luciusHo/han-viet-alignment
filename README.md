# han-viet-alignment
Xây dựng dữ liệu dóng hàng Hán–Việt từ sắc phong Hưng Yên tập 1/3 và Minh Mệnh chính yếu tập 4/5/6.

**Trạng thái: khung dự án và hợp đồng dữ liệu. Chưa có pipeline OCR/dóng hàng hoặc sản phẩm nộp.**
Nhóm bốn thành viên; ưu tiên GPU laptop và công cụ miễn phí, OCR backend chưa chốt.

## Bắt đầu
```sh
python3 scripts/check_scaffold.py
```
Python ≥3.11, không cần dependency cho bước kiểm tra khung.
Đọc [USER_GUIDE.md](USER_GUIDE.md), [yêu cầu](docs/requirements.md),
[hợp đồng dữ liệu](docs/contract.md) và [quyết định](docs/decisions.md).

## Tổ chức
- configs/: cấu hình dự kiến chung, hai nhóm sách và năm mã sách.
- src/han_viet_alignment/: common, inventory, extraction, sac_phong, minh_menh,
  alignment, review, validation, export. Hiện chỉ có mô tả trách nhiệm module.
- scripts/: kiểm tra khung; các runner sẽ thêm khi thực sự triển khai.
- tests/: vị trí kiểm thử và fixtures nhỏ cho giai đoạn triển khai.
- docs/: yêu cầu, hợp đồng, quyết định, kết quả pilot chưa chạy.
- metadata/: danh mục sách, thành viên, mẫu bảng kiểm kê/truy vết/hiệu đính.
- docs-local/: tài liệu nguồn và từ điển local, không commit.
- workspace/: dữ liệu xử lý và gói xuất local, không commit.

## Hai nhóm sách
| Mã | Sách | Hán | Việt | Phiên âm |
| --- | --- | --- | --- | --- |
| R1001/R1003 | Sắc phong tập 1/3 | OCR | OCR | Có |
| R1204/R1205/R1206 | Minh Mệnh tập 4/5/6 | OCR | Trích lớp text, đối chiếu ảnh | Không |

Cả năm tập thuộc loại cần OCR. Chỉ tiêu nhóm: 8.000 cặp hợp lệ, tối thiểu 2.000/người.
Tài liệu hành chính thay phần bàn giao/đánh giá của quy định chung.
Giữ bản dịch sách, không dịch bù; OCR thô tách text sạch; truy vết theo doc_id.
Cấu trúc bàn giao 01_nguon–04_dong_hang được tạo riêng khi triển khai export.

## Cộng tác
Thành viên đã cung cấp: @ahihitoanne (Phạm Đức Toàn), @TrongKiennn (Mạnh Trọng Kiên),
@vmq-16 (Vũ Minh Quang), leader @AIVIETNAM-AIO-luciusHo (Hồ Văn Lực; quyền GitHub chưa kiểm chứng).
Team A: @ahihitoanne và @TrongKiennn phụ trách R1001/R1003.
Team B: @vmq-16 và leader phụ trách R1204/R1205/R1206.
Hạn nộp, thông tin báo cáo và phân công từng văn bản chưa chốt. Xem metadata/team.json.
Leader là CODEOWNER toàn repo; quy trình review và bảo vệ nhánh trong [governance](docs/governance.md).
PR phải nêu phạm vi và cách kiểm tra; không thêm dữ liệu lớn hoặc bí mật.
CI hiện chỉ kiểm tra khung, không xác nhận chất lượng dóng hàng.

## Đặc tả đang review
- [Constitution dự thảo](.specify/memory/constitution.md) — PROPOSED, chưa phê chuẩn.
- [F01: hợp đồng chung](specs/001-shared-data-contract/spec.md) và [contract trung gian](specs/001-shared-data-contract/contracts/intermediate.md).
Chưa khởi tạo Spec Kit CLI/integration; các tài liệu trên được soạn trước để review.
Chưa triển khai F01 hoặc pipeline. Điểm cần chốt nằm trong bảng NC01–NC08 của spec.
