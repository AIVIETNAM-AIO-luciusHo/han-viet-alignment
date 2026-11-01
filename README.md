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

## Cây thư mục hiện tại
```text
han-viet-alignment/
├── .github/
│   ├── CODEOWNERS
│   ├── workflows/ci.yml
│   └── pull_request_template.md
├── .agents/skills/                  # Codex Spec Kit skills
├── .specify/
│   ├── memory/constitution.md       # Constitution dự thảo
│   ├── templates/
│   ├── scripts/bash/
│   ├── workflows/
│   ├── integrations/
│   ├── init-options.json
│   └── integration.json
├── configs/
│   ├── base.yaml
│   ├── sac_phong.yaml
│   ├── minh_menh.yaml
│   └── books/                      # R1001, R1003, R1204, R1205, R1206.yaml
├── src/
│   └── han_viet_alignment/
│       ├── __init__.py
│       ├── common/
│       ├── inventory/
│       ├── extraction/
│       ├── sac_phong/
│       ├── minh_menh/
│       ├── alignment/
│       ├── review/
│       ├── validation/
│       └── export/
├── scripts/
│   ├── check_scaffold.py
│   ├── check_project.py
│   └── check_tooling.py            # Tùy chọn, độc lập CI bắt buộc
├── tests/
│   ├── README.md
│   ├── common/
│   ├── tooling/                    # Kiểm thử tooling tùy chọn
│   ├── sac_phong/
│   ├── minh_menh/
│   ├── validation/
│   ├── integration/
│   └── fixtures/
├── docs/
│   ├── requirements.md
│   ├── contract.md
│   ├── decisions.md
│   ├── governance.md
│   └── pilot_results.md
├── specs/
│   └── 001-shared-data-contract/
│       ├── spec.md
│       ├── contracts/intermediate.md
│       └── checklists/requirements.md
├── metadata/
│   ├── README.md
│   ├── books.json
│   ├── team.json
│   ├── documents.tsv
│   ├── source_regions.tsv
│   ├── corrections.tsv
│   ├── assignments.tsv
│   └── quality_reviews.tsv
├── docs-local/                     # Local, không commit
├── workspace/                      # Local, không commit; tạo khi cần
├── .gitignore
├── README.md
├── USER_GUIDE.md
├── requirements-ci.txt
├── requirements-tools.txt
└── pyproject.toml
```
Các module trong package hiện chỉ có `__init__.py` mô tả trách nhiệm;
`tests/common/` có test cấu hình; các thư mục còn lại giữ chỗ, chưa có fixture OCR thật.
`docs/` chứa quy định và quyết định chung; `specs/` chứa đặc tả theo feature;
`.specify/memory/` chứa constitution dự thảo.

Tên repository dùng `han-viet-alignment`, tên package Python dùng `han_viet_alignment`.
Các module dùng `snake_case` không dấu: `sac_phong`, `minh_menh`.
Đường dẫn code chuẩn luôn bắt đầu bằng `src/han_viet_alignment/`;
`tests/` nhóm theo chức năng, không bắt buộc lặp lại tên package.
Chỉ thêm thư mục test và runner khi có chức năng cần kiểm tra/chạy;
`run_pilot.py`, `run_sac_phong.py`, `run_minh_menh.py`, `build_submission.py`
chưa tồn tại, chưa phải lệnh được hỗ trợ.

Cây này mô tả repo phát triển. Cây bàn giao `01_nguon`–`04_dong_hang`
được quy định riêng trong [hợp đồng dữ liệu](docs/contract.md), chưa được sinh ra.

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
Thành viên đã cung cấp: @ahihitoanne (Phạm Đức Toàn), @TrongKiennn (Mạnh Trọng Kiên),
@vmq-16 (Vũ Minh Quang), leader @AIVIETNAM-AIO-luciusHo (Hồ Văn Lực; quyền GitHub chưa kiểm chứng).
Team A: @ahihitoanne và @TrongKiennn phụ trách R1001/R1003.
Team B: @vmq-16 và leader phụ trách R1204/R1205/R1206.
Hạn nộp, thông tin báo cáo và phân công từng văn bản chưa chốt. Xem metadata/team.json.
Leader là CODEOWNER toàn repo; quy trình review và bảo vệ nhánh trong [governance](docs/governance.md).
PR phải nêu phạm vi và cách kiểm tra; không thêm dữ liệu lớn hoặc bí mật.
CI kiểm tra khung/cấu hình/test cấu hình, không xác nhận chất lượng dóng hàng.

## Đặc tả đang review
- [Constitution dự thảo](.specify/memory/constitution.md) — PROPOSED, chưa phê chuẩn.
- [F01: hợp đồng chung](specs/001-shared-data-contract/spec.md) và [contract trung gian](specs/001-shared-data-contract/contracts/intermediate.md).
Đã tích hợp Spec Kit 1.2.5 với Codex skills; thành viên không cần cài công cụ AI.
Chưa triển khai F01 hoặc pipeline. Điểm cần chốt nằm trong bảng NC01–NC08 của spec.

CI bắt buộc không cần Codex/Spec Kit hoặc các thư mục agent. Thành viên dùng editor bất kỳ
vẫn chạy kiểm tra dự án và mở PR; xem [hướng dẫn thành viên](USER_GUIDE.md#kiểm-tra-trước-khi-mở-pr).
