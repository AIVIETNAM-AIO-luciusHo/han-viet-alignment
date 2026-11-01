# F01 — Hợp đồng dữ liệu và cấu hình chung

Trạng thái: PROPOSED, chưa triển khai | Ngày: 2026-11-01
Owner đề xuất: leader; reviewer: Team A và Team B.
Căn cứ: docs/contract.md, docs/requirements.md, metadata/books.json,
.specify/memory/constitution.md và quy định gốc được liệt kê trong constitution.

## Vấn đề và mục tiêu
Hai luồng sách có thành phần khác nhau nhưng phải bàn giao một schema duy nhất.
Repo mới có mô tả module và hợp đồng TSV; chưa có giao diện trung gian, truy vết cấp cặp,
bộ nạp cấu hình hoặc cơ chế kiểm tra tương thích. F01 xác định chúng trước khi code song song.
Mọi nội dung thiết kế dưới đây là PROPOSED trừ mục ghi CONFIRMED.

## Phạm vi
Đặc tả kiểu dữ liệu trung gian, ranh giới bước, cấu hình, lỗi và tiêu chí contract test.
Không bao gồm engine OCR, thuật toán dóng hàng, UI hiệu đính, exporter hoàn chỉnh,
chạy sách hàng loạt, sản lượng từng thành viên hoặc thay đổi quản trị GitHub.
Không sửa package hay các bảng metadata hiện có ở giai đoạn đặc tả.

## User stories và acceptance scenarios
### US1 — Hai team trao đổi dữ liệu cùng hợp đồng (P1)
Cho văn bản có Hán/phiên âm/Việt hoặc Hán/Việt, khi adapter tạo dữ liệu trung gian,
consumer dùng cùng schema mà không phụ thuộc tên sách hay backend.
- Sắc phong có phiên âm; thiếu phiên âm phải được báo, không lặng lẽ bỏ qua.
- Sách không phiên âm dùng trạng thái not_applicable, không tạo text giả.
- book_id không thuộc danh mục phải bị từ chối; không tự đăng ký mã.

### US2 — Reviewer truy ngược từng cặp (P1)
Cho một cặp chứa nhiều đoạn hoặc qua trang, reviewer truy được tất cả đoạn sạch,
artifact thô và trang/vùng nguồn, kể cả sau hiệu đính.
- Thiếu trang/box không được thay bằng giá trị giả; kết quả bị đánh dấu thiếu truy vết.
- Sửa text tạo revision và correction, không thay bytes của artifact OCR thô.

### US3 — Chạy cùng đặc tả trên máy khác (P1)
Cho hai máy có source root khác nhau, khi resolve cùng cấu hình và cùng hash nguồn,
thuộc tính sách/contract giống nhau; chỉ đường dẫn local và thiết bị được phép khác.
- Backend chưa chọn phải báo chưa cấu hình tại bước OCR, không tự gọi dịch vụ mạng.
- YAML/JSON mâu thuẫn thuộc tính sách phải có lỗi rõ, không âm thầm chọn một giá trị.

### US4 — Kiểm tra trước bàn giao (P2)
Dữ liệu hai team chiếu ra cùng bảy cột, giữ thứ tự; mọi provenance nằm ở sidecar nội bộ.
Schema hợp lệ nhưng chưa review ngữ nghĩa không được ghi là đạt nghiệm thu.

## Yêu cầu chức năng
| ID | Yêu cầu | Căn cứ/trạng thái |
| --- | --- | --- |
| FR01 | ID văn bản/câu và thứ tự theo docs/contract.md | CONFIRMED, hướng dẫn mục 3 và danh sách |
| FR02 | Đầu ra bàn giao 7 cột, UTF-8/NFC/LF, XLSX DONG_HANG đồng nhất | CONFIRMED, mục 3 |
| FR03 | Khai báo có/không phiên âm theo danh mục, không theo tên thư mục | CONFIRMED, DANH_SACH_SACH |
| FR04 | Giữ thô/sạch/aligned riêng; sửa có lý do và nguồn | CONFIRMED, mục 2–4 |
| FR05 | Liên kết cặp→đoạn→artifact→vùng; hỗ trợ nhiều nguồn/cặp | PROPOSED |
| FR06 | Version schema, run manifest và lỗi có mã ổn định | PROPOSED |
| FR07 | Resolve config xác định, đường dẫn portable, kiểm tra mâu thuẫn | PROPOSED |
| FR08 | Chặn tự dịch bù, chuyển giản/phồn hoặc dịch vụ ngoài ngầm | CONFIRMED, mục 1/3 và leader |
| FR09 | Phân biệt lỗi định dạng, chỉ số tự động và review ngữ nghĩa | CONFIRMED, mục 6–8 |
| FR10 | Không đếm dòng khuyết vào chỉ tiêu; thiếu bằng chứng review không tự chứng nhận hợp lệ | CONFIRMED/biện pháp PROPOSED |

## Ranh giới module và input/output — PROPOSED
| Bước | Input | Output | Trách nhiệm |
| --- | --- | --- | --- |
| inventory | danh mục, PDF, phạm vi đã xác nhận | Document, SourceRegion | Gán doc_id và thứ tự, không OCR |
| extraction | nguồn/vùng, config backend | RawArtifact, RunManifest | Render/trích text/OCR; giữ nguyên kết quả thô |
| sac_phong/minh_menh | inventory + artifact thô | CleanSegment + tham chiếu nguồn | Bố cục, tách thành phần, đặc thù sách; gọi thuật toán chung |
| alignment | segment Hán và Việt, phiên âm khi có | AlignmentCandidate | Tạo ứng viên, không tự sửa bản dịch |
| review | ứng viên, nguồn, nhận xét | revision/correction + quyết định reviewer | Hiệu đính; không ghi đè thô |
| validation | dữ liệu + danh mục/từ điển + review | ValidationReport | Schema, độ phủ, chỉ số; không tự phán ngữ nghĩa |
| export | snapshot đã kiểm tra | TSV/XLSX/gói nộp | Chiếu 7 cột; không thêm provenance vào TSV |

Chi tiết đối tượng và versioning trong contracts/intermediate.md.
common sở hữu định nghĩa dùng chung, không chứa logic if/else theo mã sách.
Hai team không tự tạo loader/validator/exporter khác nhau.

## Cấu hình — PROPOSED
metadata/books.json là nguồn chuẩn thuộc tính sách, đối chiếu danh sách chính thức.
YAML chọn policy chạy; các thuộc tính sách lặp trong YAML phải bằng danh mục hoặc báo lỗi.
Thứ tự policy: base → family → book → override runtime tường minh.
Danh sách thay toàn bộ, scalar thay giá trị, mapping merge theo khóa; kiểu sai/khóa lạ bị từ chối.
Null chỉ hợp lệ cho trường optional (ví dụ backend chưa chọn); không xóa required field bằng null.
Override không được đổi book_id/has_phien_am hoặc làm yếu ngưỡng quy định.
Source root truyền từ môi trường/CLI; đường dẫn nguồn tương đối, không hard-code máy cá nhân.
Backend và device chọn cấu hình; CPU không khả thi với model thì báo rõ, không giả định fallback thành công.
Trước mỗi run lưu config đã resolve đã loại secret, hash nguồn và tool/model versions.
Chưa có bộ nạp thực thi cơ chế này.

## Edge cases
- Câu qua nhiều trang, trang có nhiều văn bản; một vùng cung cấp nhiều đoạn.
- Không có phiên âm khác với có phiên âm nhưng thiếu do OCR.
- Mốc a/b thiếu/lặp: không ghép chắc chắn; chuyển manual review.
- Chữ ngoài từ điển, dòng lệch số chữ/âm tiết: tính theo công thức gốc, không bỏ để tăng điểm.
- Trùng ID, ID lệch sách, thứ tự thiếu/lặp, nguồn thay hash: lỗi có vị trí và nguyên nhân.
- □/[...] vẫn lưu để bảo toàn độ phủ; không tính sản lượng hợp lệ.
- Mẫu số chỉ số bằng 0: not_evaluated/not_applicable theo lý do, không 100%.
- Thay ranh giới câu sau hiệu đính: giữ candidate_id; tạo snapshot và bảng ánh xạ ID cũ/mới.

## Thành công và kiểm chứng — PROPOSED
SC01: cùng một bộ contract test nhận đầu ra hợp lệ của cả hai family adapter.
SC02: mọi ứng viên trong fixture truy được nguồn hoặc có lỗi thiếu truy vết tường minh;
không có kết quả ready_for_export khi còn nguồn bắt buộc bị thiếu.
SC03: phát hiện các trường hợp ID/config/schema sai mà không cần cài OCR/GPU.
SC04: các case TSV encoding/7 cột, missing readings theo sách, mismatch XLSX,
□/[...], mẫu số 0 được kiểm tra độc lập với số lượng cặp/ngưỡng ngữ nghĩa.
SC05: đủ coverage mẫu cho cả 5 sách trước khi kết thúc pilot, không yêu cầu
đưa trang sách vào Git khi chưa có quyền. Fixture synthetic cho CI, mẫu thật để local.
SC06: không thay artifact thô sau correction; raw hash trước/sau giống nhau.
Chưa có kết quả thực nghiệm chứng minh các tiêu chí này đạt.

## Dependency và triển khai song song
F01 có thể duyệt giao diện tối thiểu trước: IDs, Document/Segment/Candidate,
provenance, config authority và lỗi. Sau đó F02 kiểm kê và F03/F04 pilot chạy song song.
F05 kiểm định/hiệu đính và F06 export dùng lại cùng hợp đồng; không chờ chọn backend cuối.
Thay schema trong lúc pilot phải có review hai team và leader, kèm migration nếu ảnh hưởng dữ liệu.

## Điểm cần xác nhận
| ID | Nội dung | Người xác nhận | Tác động |
| --- | --- | --- | --- |
| NC01 | Phê chuẩn constitution/F01 và hợp đồng trung gian | Leader + hai team review | Chặn đóng băng giao diện |
| NC02 | Nguồn chuẩn metadata/config và quy tắc merge đề xuất | Leader | Chặn implement loader |
| NC03 | JSONL sidecar và lifecycle/versioning đề xuất | Leader + hai team | Chặn serializer chung |
| NC04 | Phạm vi chính thức và hạn nộp | Giảng viên/người giao sách | Chặn chạy hàng loạt, không chặn khảo sát mẫu |
| NC05 | Cỡ mẫu/cách lấy mẫu nghiệm thu, quy tắc gán sản lượng | Giảng viên | Chặn tuyên bố nghiệm thu, không tự đặt |
| NC06 | phien_am.txt rỗng hay marker-only cho sách không phiên âm | Người giao sách | Chặn hoàn thiện packaging |
| NC07 | GPU/VRAM/OS, backend và quyền gửi dữ liệu ngoài | Leader | Chặn chọn backend production |
| NC08 | Phiên bản Spec Kit/integration và phê chuẩn draft | Leader | Chặn khởi tạo công cụ |

Tất cả NC01–NC08: NEEDS_CONFIRMATION. Không coi lựa chọn PROPOSED là quyết định đã duyệt.
