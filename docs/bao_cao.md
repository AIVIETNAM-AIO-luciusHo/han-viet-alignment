# BÁO CÁO ĐỒ ÁN: XÂY DỰNG DỮ LIỆU SONG SONG HÁN – VIỆT VĂN BẢN HÀNH CHÍNH

**Đề tài:** Dóng hàng Hán – Việt cấp câu cho sắc phong Hưng Yên (tập 1, 3) và *Minh Mệnh chính yếu* (tập 4, 5, 6)

**Tên file nộp:** `24120374_24120128_22120167_24120467.zip` / `24120374_24120128_22120167_24120467_report.pdf`
<!-- TODO: xác nhận lại thứ tự MSSV trong tên file theo quy định của thầy -->

**Mã nguồn:** `source.zip` (repository `han-viet-alignment`)

---

## 1. Thông tin thành viên

| STT | Họ và tên | MSSV | Email sinh viên | Nhóm con | Vai trò |
| --- | --- | --- | --- | --- | --- |
| 1 | Hồ Văn Lực | 24120374 | 24120374@student.hcmus.edu.vn | B – Minh Mệnh | Nhóm trưởng |
| 2 | Vũ Minh Quang | 24120128 | 24120128@student.hcmus.edu.vn | B – Minh Mệnh | Thành viên |
| 3 | Mạnh Trọng Kiên | 22120167 | 22120167@student.hcmus.edu.vn | A – Sắc phong | Thành viên |
| 4 | Phạm Đức Toàn | 24120467 | 24120467@student.hcmus.edu.vn | A – Sắc phong | Thành viên |

## 2. Phân công công việc

### 2.1. Phân công theo sách và công đoạn

| Thành viên | Sách | Công đoạn chính |
| --- | --- | --- |
| Phạm Đức Toàn | R1001, R1003 | Trích xuất PDF, phân tích bố cục, OCR Hán và Việt, sinh `02_ocr_tho`, `03_text_sach` (`ocr_tho.py`, `sac_phong/`) |
| Mạnh Trọng Kiên | R1001, R1003 | Làm sạch, tách câu, dóng hàng Hán ↔ phiên âm ↔ dịch nghĩa, sửa lỗi OCR theo từ điển, xuất TSV/XLSX (`dong_hang.py`, `alignment/`, `export/`) |
| Vũ Minh Quang | R1204, R1205, R1206 | <!-- TODO --> |
| Hồ Văn Lực | R1204, R1205, R1206 | Quản lý repo, hợp đồng dữ liệu, metadata văn bản (`metadata/documents.tsv`), <!-- TODO --> |

### 2.2. Phân công đến văn bản và số cặp

<!-- TODO: điền sau khi hoàn thành; số cặp hợp lệ = không chứa □ hoặc [...] -->

| Thành viên | Sách | Văn bản (doc_id) | Số cặp | Số cặp hợp lệ |
| --- | --- | --- | --- | --- |
| Phạm Đức Toàn | R1001 / R1003 | R1001.xxx – R1001.yyy | | |
| Mạnh Trọng Kiên | R1001 / R1003 | | | |
| Vũ Minh Quang | R1204–R1206 | | | |
| Hồ Văn Lực | R1204–R1206 | | | |
| **Tổng** | | | | **(chỉ tiêu ≥ 8.000)** |

## 3. Nguồn tài liệu

| Mã sách | Tên sách | File PDF được giao | Số trang PDF | Phạm vi xử lý | Hán | Phiên âm | Dịch nghĩa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R1001 | Sắc phong trên địa bàn tỉnh Hưng Yên – tập 1 | `10.1 - sac phong hung yen.pdf` | 178 | Trang 4–178 | Scan (OCR) | Scan (OCR) | Scan (OCR) |
| R1003 | Sắc phong trên địa bàn tỉnh Hưng Yên – tập 3 | `10.3 - sac phong hung yen.pdf` | 252 | Trang 5–252 | Scan (OCR) | Scan (OCR) | Scan (OCR) |
| R1204 | Minh Mệnh chính yếu – tập 4 | `Minh Mệnh chính yếu tập 4_ocr.pdf` | 516 | <!-- TODO --> | Scan (OCR) | Không có | Lớp text PDF, đối chiếu ảnh |
| R1205 | Minh Mệnh chính yếu – tập 5 | `Minh Mệnh chính yếu tập 5_ocr.pdf` | 566 | <!-- TODO --> | Scan (OCR) | Không có | Lớp text PDF, đối chiếu ảnh |
| R1206 | Minh Mệnh chính yếu – tập 6 | `Minh Mệnh chính yếu tập 6_ocr.pdf` | 736 | <!-- TODO --> | Scan (OCR) | Không có | Lớp text PDF, đối chiếu ảnh |

Tài nguyên hỗ trợ do người giao sách cung cấp:
- Từ điển âm Hán-Việt `QuocNgu_SinoNom_TongHop3.xlsx` (dùng để dóng hàng và đánh giá độ khớp âm).
- Từ điển chữ Hán gần giống hình dạng `SinoNom_Similar_Dic_v2.xlsx` (dùng để sửa lỗi OCR chữ Hán).
- Dữ liệu mẫu `MAU_parallel.tsv/.xlsx` và script kiểm tra `kiem_tra_du_lieu.py`.

Chất lượng nguồn: <!-- TODO: số trang mờ/rách; xác nhận < 20% hoặc đã liên hệ người giao sách -->

Chỉnh sửa ảnh so với PDF gốc: <!-- TODO: nếu có xoay/làm nét → nêu và nộp <MA_SACH>_updated.pdf; nếu chỉ cắt ảnh theo văn bản (<doc_id>_<k>.jpg) thì ghi rõ -->

## 4. Quy trình thực hiện

Toàn bộ quy trình được tự động hóa bằng Python; con người chỉ hiệu đính các dòng được hệ thống gắn cờ.

```text
PDF scan ─► [1] Trích ảnh trang ─► [2] Phân tích bố cục, cắt theo văn bản ─► [3] OCR Hán / OCR Việt
        ─► [4] Làm sạch ─► [5] Tách câu ─► [6] Dóng hàng + sửa lỗi OCR ─► [7] Hiệu đính ─► [8] Kiểm tra, xuất TSV/XLSX
```

### 4.1. Nhóm A – Sắc phong (R1001, R1003)

**Bước 1 – Trích xuất ảnh** (`sac_phong/pdf_extractor.py`): lấy trực tiếp luồng JPEG nhúng trong PDF, giữ nguyên độ phân giải scan gốc (3312×2336), không nén lại.

**Bước 2 – Phân tích bố cục và cắt ảnh** (`sac_phong/layout_parser.py`): phân loại hai kiểu trang dựa trên độ sáng điểm ảnh:
- *Layout A*: một sắc phong/trang – ảnh bản Hán ở trên, phiên âm và dịch nghĩa ở dưới.
- *Layout B*: hai sắc phong/trang – hai ảnh Hán bên trái, hai khối Quốc ngữ bên phải.

Mỗi văn bản được gán `doc_id = <MA_SACH>.<số thứ tự 3 chữ số>` và lưu ảnh `han/<doc_id>_1.jpg`, `viet/<doc_id>_1.jpg`.

**Bước 3 – OCR** (`sac_phong/ocr_pipeline.py`):

| Phần | Phát hiện vùng chữ | Nhận dạng | Ghi chú |
| --- | --- | --- | --- |
| Chữ Hán | PP-OCRv6 medium (ONNX, chạy qua RapidOCR) | PP-OCRv6 medium | Model tải từ HuggingFace `haotruong-hitlab/pp-ocrv6-medium-onnx`; dự phòng RapidOCR mặc định (PP-OCRv4) |
| Quốc ngữ | RapidOCR (phát hiện dòng) | VietOCR `vgg_transformer` | Tách phiên âm và dịch nghĩa theo tiêu đề khối |

Kết quả thô lưu ở `02_ocr_tho/{han,viet}/<doc_id>.txt` và `Label.txt`, `fileState.txt` theo định dạng PPOCRLabel (mỗi box đúng 4 điểm; Hán theo cột phải→trái, trên→dưới; Việt trên→dưới). OCR thô không sửa tay.

**Bước 4 – Làm sạch** (`alignment/cleaning.py`, `alignment/han_filter.py`):
- Bỏ tiêu đề trang, số trang, chỉ mục chú thích ([1], (1)…), ký tự rác.
- Ghép âm tiết bị OCR tách đôi (vd *Hù ng* → *Hùng*) khi từ điển xác nhận.
- Loại cột chữ Hán rác (hoa văn, ấn triện, viền) khi thỏa đồng thời: điểm nhận dạng thấp **và** tỉ lệ khớp âm với phiên âm thấp. Danh sách dòng bị loại được ghi lại để người xác nhận.

**Bước 5 – Tách câu** (`alignment/segment.py`):
- Phiên âm tách tại `. ! ?`; dịch nghĩa tách tại `. ! ? ;`.
- Bổ sung điểm tách theo công thức cố định của sắc phong (*Hướng lai*, *Tứ kim*, *Khâm tai*, *Kính cẩn thay*, *Ngày … tháng …*) khi OCR làm mất dấu câu.
- Gộp mảnh không đứng riêng được (tiêu đề 1–2 âm tiết như *Sắc.*, mảnh viết thường sau câu rất ngắn).

**Bước 6 – Dóng hàng** (`alignment/pa_dn.py`, `alignment/han_pa.py`, `alignment/correction.py`):
1. *Phiên âm ↔ dịch nghĩa* (cấp câu): quy hoạch động kiểu Gale–Church có bổ sung từ vựng – từ chung (tên riêng, chức danh, niên hiệu), mốc neo (*Khâm tai* ↔ *Kính thay*, dòng niên đại ↔ *Ngày … năm … (19xx)*), tỉ lệ độ dài ước lượng theo từng văn bản. Hạt cho phép: 1–1, 1–2, 2–1, 2–2, 1–3, 3–1.
2. *Hán ↔ phiên âm* (cấp chữ – âm tiết): edit distance có từ điển (chữ khớp âm theo `QuocNgu_SinoNom_TongHop3.xlsx` có chi phí 0), sau đó chiếu ranh giới câu phiên âm sang bản Hán. Đảm bảo số chữ Hán (kể cả □) = số âm tiết trên mỗi dòng.
3. *Sửa lỗi OCR có bằng chứng*, theo thứ tự: sửa âm tiết OCR hỏng theo chữ Hán → sửa dấu thanh khi sách đọc đúng ở chỗ khác → thay chữ Hán gần giống hình dạng có đúng âm → bộ nhớ cụm từ đã khớp trong sách → nếu không có bằng chứng thì ghi □ và lưu chữ gốc vào `ghi_chu`.
4. Bắc cầu thành Hán ↔ dịch nghĩa.

**Bước 7 – Hiệu đính:** hệ thống sinh `review.tsv` liệt kê dòng có cờ cảnh báo (`LECH_SO_CHU`, `KHOP_AM_DUOI_95`, `GOP_NHIEU_CAU`, `GIAN_THE`, `THIEU_DICH`, `OCR_THIEU_CHU`…). Người hiệu đính đối chiếu ảnh gốc, sửa trên file XLSX rồi chạy `dong_hang.py --sync xlsx` để chuẩn hóa và đồng bộ lại TSV.

**Bước 8 – Kiểm tra và xuất file** (`export/writer.py`): TSV và XLSX 7 cột (`sent_id, doc_id, doc_type, han, phien_am, dich_nghia, ghi_chu`), UTF-8 không BOM, NFC, LF; XLSX một sheet `DONG_HANG`, ô dạng text, không công thức. Kiểm tra cuối bằng `kiem_tra_du_lieu.py`.

### 4.2. Nhóm B – Minh Mệnh chính yếu (R1204, R1205, R1206)

<!-- TODO: nhóm B mô tả: cách xác định ranh giới văn bản (309 doc_id cho R1204), OCR Hán, trích lớp text Việt và đối chiếu ảnh, tách câu, dóng Hán ↔ dịch nghĩa khi không có phiên âm -->

### 4.3. Nguyên tắc tuân thủ

- Giữ nguyên bản dịch của sách; **không dùng LLM hay công cụ dịch** để dịch bù, viết lại, sửa văn phong.
- Không tự chuyển giản ↔ phồn; chữ giản thể do OCR sinh ra được gắn cờ `GIAN_THE` để sửa theo ảnh gốc.
- Chữ không đọc được ghi □ (mỗi chữ một ký hiệu, ở cả `han` và `phien_am`); đoạn dịch khuyết ghi `[...]`; lý do ghi ở `ghi_chu`.
- Mọi file đặt tên theo `doc_id` để truy vết từ câu → văn bản → ảnh → OCR thô.

## 5. Công cụ, mô hình và môi trường

| Hạng mục | Công cụ / phiên bản |
| --- | --- |
| Ngôn ngữ | Python 3.12 |
| Hệ điều hành | Windows 11 <!-- TODO: thêm máy của nhóm B nếu khác --> |
| Phần cứng | RAM 16 GB, chạy trên CPU (không dùng GPU) <!-- TODO: thêm CPU; máy của nhóm B nếu khác --> |
| OCR Hán | PP-OCRv6 medium (ONNX) qua `rapidocr-onnxruntime` |
| OCR Quốc ngữ | VietOCR `vgg_transformer` (PyTorch) |
| Xử lý ảnh/PDF | `pypdf`, `opencv-python`, `Pillow`, `numpy` |
| Dữ liệu bảng | `pandas`, `openpyxl` |
| Nhận diện giản thể | `opencc-python-reimplemented` (chỉ dùng bảng tra để gắn cờ, không chuyển đổi) |
| LLM / dịch vụ trả phí | Claude (Anthropic), không dùng trong pipeline OCR/dóng hàng tự động. Dùng cho: (1) gán nhãn ranh giới mẫu đánh giá Minh Mệnh (`docs/danh_gia_minh_menh/`) để chọn `--nguong-gop`; (2) qua Claude Code (Claude Opus 5.5): hỗ trợ viết code và hiệu đính sắc phong R1001/R1003 — đối chiếu ảnh trang sách để điền câu niên đại OCR bỏ sót và chép lại phiên âm/dịch nghĩa đúng như sách in cho các văn bản OCR hỏng nặng. Không dùng để dịch hay viết lại bản dịch. Chi tiết mô hình và prompt: USER_GUIDE mục 7 <!-- TODO: phiên bản mô hình và prompt của việc (1) --> |
| Kiểm tra nhãn | PPOCRLabel |

Lý do không dùng công cụ OCR Hán Nôm tại kimhannom.fit.hcmus.edu.vn: <!-- TODO: nêu lý do (vd chạy hàng loạt cục bộ, tái lập được, đã so sánh mẫu…) hoặc bổ sung nếu đã dùng -->

## 6. Thống kê kết quả

<!-- TODO: điền từ output `dong_hang.py` và `kiem_tra_du_lieu.py` -->

| Chỉ số | R1001 | R1003 | R1204 | R1205 | R1206 | Tổng |
| --- | --- | --- | --- | --- | --- | --- |
| Số văn bản | | | | | | |
| Số dòng Hán | | | | | | |
| Số dòng Việt | | | | | | |
| Số cặp | | | | | | |
| Số cặp có □ hoặc [...] | | | | | | |
| **Số cặp hợp lệ** | | | | | | |
| Độ khớp âm (≥ 95%) | | | Không áp dụng | Không áp dụng | Không áp dụng | — |

Ghi chú: *Minh Mệnh chính yếu* không có phiên âm nên chỉ số độ khớp âm **không áp dụng** (không báo 100%).

Phân bố kiểu dóng hàng: <!-- TODO: số cặp 1–1 / 1–n / n–1 / n–m -->

## 7. Tự kiểm tra chất lượng

### 7.1. Kiểm tra định dạng
- Kết quả `kiem_tra_du_lieu.py` cho từng sách: <!-- TODO: dán tóm tắt output -->
- `Label.txt` / `fileState.txt`: mọi ảnh có nhãn, mọi box đúng 4 điểm, mở được bằng PPOCRLabel (xem Phụ lục).

### 7.2. Kiểm tra ngữ nghĩa (tỷ lệ lỗi)

Lấy mẫu <!-- TODO: n --> cặp ngẫu nhiên mỗi sách, đánh giá theo 8 tiêu chí của mục 6 hướng dẫn và phân loại lỗi OMISSION / ADDITION / MISSING.

| Sách | Số cặp kiểm tra | OMISSION | ADDITION | MISSING | Tổng lỗi | Tỷ lệ lỗi (≤ 30%, mục tiêu ≤ 20%) |
| --- | --- | --- | --- | --- | --- | --- |
| R1001 | | | | | | |
| R1003 | | | | | | |
| R1204 | | | | | | |
| R1205 | | | | | | |
| R1206 | | | | | | |

Mọi lỗi phát hiện trong mẫu đã được sửa và rà soát lỗi tương tự trên toàn file. <!-- TODO: mô tả các lỗi điển hình và cách sửa -->

## 8. Khó khăn và hướng xử lý

- Bản Hán sắc phong có ấn triện đè chữ, hoa văn viền → OCR sinh chữ rác; xử lý bằng bộ lọc điểm nhận dạng + khớp âm (`han_filter.py`).
- OCR Hán đôi khi sinh chữ giản thể hoặc chữ gần giống hình dạng → sửa bằng từ điển chữ tương tự và bộ nhớ cụm từ, phần còn lại ghi □ để hiệu đính theo ảnh.
- OCR Quốc ngữ làm mất dấu câu hoặc chữ hoa → bổ sung điểm tách câu theo công thức cố định của sắc phong.
- <!-- TODO: khó khăn của nhóm B -->

## 9. Dữ liệu thêm (extras.zip)

<!-- TODO: nếu có (vd review.tsv, page_mapping.tsv, danh sách dòng Hán bị loại), mô tả nội dung; nếu không thì xóa mục này -->

## 10. Tài liệu tham khảo

1. Hướng dẫn thực hiện đồ án xây dựng dữ liệu song song Hán Nôm và Quốc ngữ.
2. Hướng dẫn thực hiện đồ án dóng hàng Hán – Việt văn bản hành chính.
3. PaddleOCR / PP-OCR – https://github.com/PaddlePaddle/PaddleOCR
4. RapidOCR – https://github.com/RapidAI/RapidOCR
5. VietOCR – https://github.com/pbcquoc/vietocr
6. W. A. Gale, K. W. Church. *A Program for Aligning Sentences in Bilingual Corpora*. Computational Linguistics, 19(1), 1993.
7. PPOCRLabel – https://github.com/PFCCLab/PPOCRLabel

---

## Phụ lục

### A. Trang Hán mở bằng PPOCRLabel
<!-- TODO: chèn ảnh, vd ![PPOCRLabel – trang Hán](images/ppocrlabel_han.png) -->
*Hình A. `R1001/02_ocr_tho/han/R1001.00x_1.jpg` mở bằng PPOCRLabel: đúng định dạng, box ôm theo từng cột, thứ tự phải → trái.*

### B. Trang Quốc ngữ mở bằng PPOCRLabel
<!-- TODO: chèn ảnh -->
*Hình B. `R1001/02_ocr_tho/viet/R1001.00x_1.jpg` mở bằng PPOCRLabel: box theo dòng, thứ tự trên → dưới.*

### C. File XLSX mở được, không lỗi font
<!-- TODO: chèn ảnh -->
*Hình C. `R1001_parallel.xlsx` (sheet `DONG_HANG`) mở bằng Excel, hiển thị đúng chữ Hán và tiếng Việt.*

### D. File TSV mở được, không lệch cột
<!-- TODO: chèn ảnh -->
*Hình D. `R1001_parallel.tsv` mở bằng <!-- Excel/LibreOffice -->, 7 cột thẳng hàng.*
