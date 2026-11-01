## han-viet-alignment
Xây dựng dữ liệu dóng hàng Hán–Việt từ sắc phong Hưng Yên tập 1/3 và Minh Mệnh chính yếu tập 4/5/6.
--
## Thành viên nhóm 
 Họ và tên | MSSV | Email sinh viên |
| --- | --- | --- | 
| **Hồ Văn Lực** | `24120374` | 24120374@student.hcmus.edu.vn | 
| **Vũ Minh Quang** | `24120128` | 24120128@student.hcmus.edu.vn |
| **Mạnh Trọng Kiên** | `22120167` | 22120167@student.hcmus.edu.vn | 
| **Phạm Đức Toàn** | `24120467` | 24120467@student.hcmus.edu.vn | 


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
--
## Directory tree
```text
han-viet-alignment/
├── .github/                    # CODEOWNERS, CI, mẫu PR
├── configs/                    # Cấu hình chung, hai nhóm sách và năm mã sách
├── src/han_viet_alignment/
│   ├── common/                 # Kiểu dữ liệu, ID, tiện ích dùng chung
│   ├── inventory/              # Kiểm kê nguồn
│   ├── extraction/             # Trích xuất PDF/OCR
│   ├── sac_phong/              # Pipeline Team A
│   ├── minh_menh/              # Pipeline Team B
│   ├── alignment/              # Dóng hàng câu
│   ├── review/                 # Hiệu đính và truy vết
│   ├── validation/             # Kiểm tra dữ liệu
│   └── export/                 # Tạo cấu trúc nộp bài
├── scripts/                    # Hiện có kiểm tra scaffold; runner sẽ thêm sau
├── tests/                      # Kiểm thử và fixtures nhỏ
├── docs/                       # Yêu cầu, contract, quyết định, pilot
├── metadata/
│   └── team.json               # Thành viên, MSSV, GitHub, nhóm
├── docs-local/                 # PDF/từ điển local, KHÔNG commit
├── workspace/                  # Dữ liệu xử lý/xuất local, KHÔNG commit
├── USER_GUIDE.md
└── README.md
```
--
## Cộng tác
Thành viên đã cung cấp: @ahihitoanne (Phạm Đức Toàn), @TrongKiennn,
@vmq-16 (Minh Mẫn), leader @AIVIETNAM-AIO-luciusHo (luluciusHo; quyền GitHub chưa kiểm chứng).
Team A: @ahihitoanne và @TrongKiennn phụ trách R1001/R1003.
Team B: @vmq-16 và leader phụ trách R1204/R1205/R1206.
Hạn nộp, thông tin báo cáo và phân công từng văn bản chưa chốt. Xem metadata/team.json.
Leader là CODEOWNER toàn repo; quy trình review và bảo vệ nhánh trong [governance](docs/governance.md).
PR phải nêu phạm vi và cách kiểm tra; không thêm dữ liệu lớn hoặc bí mật.
CI hiện chỉ kiểm tra khung, không xác nhận chất lượng dóng hàng.
