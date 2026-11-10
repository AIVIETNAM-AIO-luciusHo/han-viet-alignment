# Hướng dẫn sử dụng — chạy từ đầu đến cuối trên máy mới

Quy tắc gốc là `guideline/HUONG_DAN_DO_AN_HAN_VIET_HANH_CHINH.pdf` (gọi tắt **HD**).
Mọi chỗ máy không chắc đều để người kiểm tra; OCR và dóng hàng tự động chỉ tạo **bản nháp** (HD mục 5).

```text
PDF ──ocr_tho.py (Người 1)──► 01_nguon/ 02_ocr_tho/ 03_text_sach/
                                              │
          dong_hang.py (Người 2) ◄────────────┘
                 │
                 ▼
   04_dong_hang/<MA_SACH>_parallel.tsv + .xlsx   +   workspace/<MA_SACH>/review.tsv
                 │
   người hiệu đính sửa .xlsx  ──►  dong_hang.py --sync xlsx  ──►  kiem_tra_du_lieu.py
```

## 1. Cài đặt (một lần)
Cần Python ≥ 3.11 (đã chạy với 3.12, Windows 11). Mọi lệnh chạy **từ thư mục gốc repo**,
vì các đường dẫn model/cấu hình là tương đối.

```powershell
cd D:\NMXLNNTN\han-viet-alignment
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```
macOS/Linux thay `.\venv\Scripts\python.exe` bằng `venv/bin/python`.

## 2. Đặt dữ liệu (không commit — đã có trong .gitignore)

| Thứ cần có | Đặt ở đâu | Lấy từ |
| --- | --- | --- |
| PDF sách (`tap 1.pdf`, `tap 3.pdf`, …) | `docs-local/NLP-20261101T150232Z-1-001/NLP/` | người giao sách |
| Từ điển `QuocNgu_SinoNom_TongHop3.xlsx` | `guideline/dict/` | người giao sách |
| `kiem_tra_du_lieu.py`, `MAU_parallel.tsv/.xlsx` | `guideline/mau_du_lieu/` | thư mục mẫu của giáo viên |
| Cấu hình VietOCR `base.yml`, `vgg-transformer.yml` | `vietocr_configs/` | repo `pbcquoc/vietocr`, thư mục `config/` |
| Trọng số `vgg_transformer.pth` | `models/` | `https://vocr.vn/data/vietocr/vgg_transformer.pth` |
| Model chữ Hán PP-OCRv6 | `models/ppocrv6/` | tự tải từ HuggingFace ở lần chạy đầu |

```powershell
New-Item -ItemType Directory -Force vietocr_configs, models, guideline\dict, guideline\mau_du_lieu
Invoke-WebRequest https://raw.githubusercontent.com/pbcquoc/vietocr/master/config/base.yml -OutFile vietocr_configs\base.yml
Invoke-WebRequest https://raw.githubusercontent.com/pbcquoc/vietocr/master/config/vgg-transformer.yml -OutFile vietocr_configs\vgg-transformer.yml
Invoke-WebRequest https://vocr.vn/data/vietocr/vgg_transformer.pth -OutFile models\vgg_transformer.pth
```

> **Bắt buộc có từ điển trước khi chạy OCR.** Thiếu `guideline/dict/QuocNgu_SinoNom_TongHop3.xlsx`
> thì bước sửa chữ Hán tự động bị tắt và độ khớp âm không tính được.

## 3. Bước 1 — OCR (Người 1)
Chạy thử vài trang trước (HD bước 4), xem ảnh cắt trong `R1001/02_ocr_tho/` rồi mới chạy cả sách:
```powershell
.\venv\Scripts\python.exe ocr_tho.py --pdf "tap 1.pdf" --pages 4-7   --ma-sach R1001
.\venv\Scripts\python.exe ocr_tho.py --pdf "tap 1.pdf" --pages 4-178 --ma-sach R1001
.\venv\Scripts\python.exe ocr_tho.py --pdf "tap 3.pdf" --pages 5-252 --ma-sach R1003
```
Chỉ cần tên file PDF, script tự tìm trong `docs-local/.../NLP/`. Chạy lại sẽ dùng cache OCR
(`cache_pages/`); thêm `--force` để OCR lại từ đầu. Trong log phải thấy
`mô hình Paddle v6`; nếu thấy `RapidOCR mặc định` là tải model thất bại.

Kết quả: `R1001/01_nguon/`, `02_ocr_tho/{han,viet}/` (OCR thô, **không sửa tay**),
`03_text_sach/{han,phien_am,dich_nghia}.txt`, `page_mapping.tsv`.

Chữ Hán trong `03_text_sach/han.txt` đi qua: lọc dòng OCR rác (điểm < 0.5 **và** < 30% chữ khớp âm,
ghi vào `workspace/<MA_SACH>/han_dong_bi_loai.tsv`) → sửa chữ OCR sang chữ **giống hình** mà đúng âm
(cần `guideline/dict/SinoNom_Similar_Dic_v2.xlsx`). Không đoán chữ theo âm: chữ sai giữ nguyên, chữ thiếu ghi □.
Ngưỡng nhận dạng `text_score = 0.5` (đã đo, xem chú thích trong `ocr_pipeline.py:get_han_engine`).

## 4. Bước 2 — Dóng hàng (Người 2)
```powershell
.\venv\Scripts\python.exe dong_hang.py --ma-sach R1001
```
Script làm lần lượt:
1. **Làm sạch** (HD bước 5): bỏ tiêu đề trang VIẾT HOA, số trang, chỉ mục chú thích `[1]` `(1)` `*` `%`,
   số rác trong phiên âm, ghép âm tiết bị tách (`Hù ng` → `Hùng`, chỉ khi từ điển xác nhận).
   Giữ chữ số và năm dương lịch của bản dịch. Không sửa văn phong.
2. **Tách câu** (HD bước 6): phiên âm tại `. ! ?`; dịch nghĩa tại `. ! ? ;`. Tiêu đề 1–2 âm tiết
   (`Sắc.`) gộp vào câu sau; mảnh viết thường chỉ gộp vào câu trước khi câu trước ≤ 3 âm tiết (OCR hay mất
   chữ hoa đầu câu — tách nhỏ an toàn hơn gộp). Khi OCR mất dấu câu, tách thêm trước công thức mở câu
   (`Hướng lai`, `Tứ kim`, `Khâm tai`, `Nhưng chuẩn`…; dịch: `Nay trẫm`, `Lại chuẩn`, `Kính cẩn thay`, `Ngày 9`…).
3. **Phiên âm ↔ dịch nghĩa** (HD bước 7): quy hoạch động theo từ chung (tên riêng, niên hiệu, mỹ tự),
   mốc `Khâm tai` ↔ `Kính (cẩn) thay`, dòng niên đại ↔ `Ngày … (18xx)`, tỉ lệ độ dài.
   Cho phép 1–1, 1–n, n–1, n–m (HD 3.1); không bao giờ gộp cả văn bản thành một dòng.
4. **Hán ↔ phiên âm**: edit distance có từ điển (1 chữ = 1 âm tiết), chiếu ranh giới câu sang bản Hán.
   - Âm tiết không có chữ Hán tương ứng (OCR bỏ sót) → **một □ cho mỗi chữ**, ghi lý do ở `ghi_chu` (HD mục 3).
   - Chữ Hán thừa ở đầu/cuối văn bản (ấn triện, chữ vùng khác) → bỏ, ghi vào `review.tsv`.
   - Chữ Hán thừa **giữa** văn bản → bỏ khỏi cột `han`, ghi ở `ghi_chu` (`02_ocr_tho` giữ nguyên OCR thô).
     Mỗi dòng luôn có số chữ (kể cả □) = số âm tiết, vì dòng lệch bị tính sai **toàn bộ** chữ (HD mục 8).
   - Cặp chữ–âm lệch được xử lý theo thứ tự, chỉ khi có bằng chứng (`alignment/correction.py`):
     1. âm tiết không phải âm Hán-Việt (`Tứng`) cách âm của chữ Hán 1 ký tự → sửa phiên âm theo chữ Hán;
        sai dấu (`峻` ghi `tuần`) → sửa khi chính sách đã đọc chữ đó bằng âm đúng ở chỗ khác; nếu không thì giữ (vd 記 `Kỷ`);
     2. chữ gần giống hình dạng (`SinoNom_Similar_Dic_v2.xlsx`) có đúng âm, là ứng viên **duy nhất** đã gặp với âm
        đó trong sách (nhiều ứng viên = dị thể → không chọn, để người xem ảnh);
     3. cụm 2–4 âm tiết đã khớp trọn vẹn ở chỗ khác trong sách/dữ liệu mẫu, và **mọi lần gặp** đều viết cùng một
        kiểu (`khâm tai` → 欽哉);
     - Không bao giờ tự chuyển giản ↔ phồn. Chữ giản thể do OCR sinh ra chỉ được **nhận diện** (bảng
       `STCharacters.txt` của `opencc-python-reimplemented`), gắn cờ `GIAN_THE`, và không bao giờ được học
       vào bộ nhớ cụm từ hay đề xuất làm chữ sửa.
     4. không có bằng chứng → chữ OCR coi như không đọc được, ghi **□**, chữ gốc ghi trong `ghi_chu`.
     Mọi chỗ sửa/che đều ghi `ghi_chu` và gắn cờ trong `review.tsv`. Tắt: `--no-correct` (không sửa), `--no-mask` (không che).
5. **Xuất** `04_dong_hang/R1001_parallel.tsv` + `.xlsx` (sheet `DONG_HANG`, UTF-8 không BOM, NFC, LF)
   và chạy luôn `guideline/mau_du_lieu/kiem_tra_du_lieu.py`.

Nguồn chữ Hán: mặc định `--han-source auto` dùng `03_text_sach/han.txt`, nếu khối nào rỗng/toàn □
hoặc OCR thô `02_ocr_tho/han/<doc_id>.txt` khớp âm phiên âm nhiều hơn thì lấy OCR thô. Ép dùng OCR thô: `--han-source raw`.

Script **không ghi đè** `04_dong_hang` đã có (tránh mất bản sửa tay). Muốn tạo lại bản nháp: thêm `--force`.

## 5. Bước 3 — Hiệu đính (người làm, bắt buộc)
Mở `workspace/R1001/review.tsv` (danh sách việc) và `R1001/04_dong_hang/R1001_parallel.xlsx` (nơi sửa).
Đối chiếu ảnh `02_ocr_tho/{han,viet}/<doc_id>_1.jpg` và `page_mapping.tsv` (số trang PDF/sách).

| Cờ trong review.tsv | Nghĩa | Cách sửa (theo HD) |
| --- | --- | --- |
| `LECH_SO_CHU(a/b)` | a chữ Hán, b âm tiết | Thêm/bớt chữ theo ảnh đến khi bằng nhau |
| `KHOP_AM_DUOI_95` | cột `chu_lech` liệt kê chữ ≠ âm | Chữ Hán sai/giản thể → sửa theo ảnh; phiên âm sách sai âm → sửa theo chữ Hán **và ghi `ghi_chu`** |
| `OCR_THIEU_CHU(n)` | đã chèn n □ vì OCR bỏ sót | Nhập chữ từ ảnh thay □, rồi xóa câu tương ứng trong `ghi_chu` |
| `THIEU_HAN` | OCR không ra chữ Hán nào | Nhập toàn bộ chữ Hán của câu từ ảnh |
| `THIEU_DICH` | OCR bản dịch rỗng → `[...]` | Nhập bản dịch **của sách** từ ảnh (không tự dịch, không dùng LLM) |
| `GOP_NHIEU_CAU` | một dòng gộp >2 câu | Kiểm tra có tách nhỏ hơn mà vẫn đúng nghĩa được không (HD 3.1) |
| `BO_CHU_HAN_THUA_*(…)` | chữ đã bỏ ở đầu/cuối | Xác nhận đó là rác; nếu là chữ thật thì thêm lại |
| `BO_CHU_THUA(…)` | chữ thừa giữa câu đã bỏ | Nếu là chữ thật (phiên âm bị OCR mất âm tiết) → thêm lại cả chữ Hán **và** âm tiết |
| `SUA_HAN(n)` / `SUA_PA(n)` | đã tự sửa n chữ Hán / âm tiết | Đối chiếu ảnh xác nhận chỗ sửa ghi trong `ghi_chu` |
| `CHE_CHU_SAI(n)` | n chữ OCR lệch âm đã thay □ | Nhập chữ đúng từ ảnh thay □ (chữ OCR cũ ở `ghi_chu`) |
| `PA_THIEU_AM(n)` | đoạn ≥ 2 chữ Hán không có âm tiết → □ ở cả `han` và `phien_am` | Nhập lại âm tiết bị OCR mất và chữ Hán từ ảnh |
| `LECH_MOC_KET` / `LECH_MOC_NGAY` | chỉ một vế có `Khâm tai`/`Kính cẩn thay` hoặc dòng niên đại | Cặp phiên âm ↔ dịch có thể lệch câu: sửa ranh giới |
| `LECH_DO_DAI` / `THIEU_TEN_RIENG` | độ dài bất thường / tên riêng phiên âm không có trong bản dịch | Kiểm tra thiếu/thừa ý (OMISSION/ADDITION, HD mục 7) |
| `GIAN_THE(钱→錢,…)` | chữ giản thể do OCR sinh ra (script chấm vẫn tính khớp vì từ điển có giản thể) | Sửa về chữ gốc **theo ảnh**; gợi ý sau `→` có thể nhiều chữ (`发→發/髮`), không đổi máy móc |
| `KHAC_DAU(chữ/âm)` | âm sách chỉ khác dấu với từ điển | Phiên âm sách in sai → sửa theo chữ Hán + `ghi_chu`; cách đọc riêng của sách → giữ |

Quy tắc nội dung cần nhớ (HD mục 3):
- `han`: viết liền, giữ phồn thể/dị thể/chữ số đại tự (拾, 貳…); OCR ra giản thể (东, 时, 经…) **phải sửa về chữ gốc**.
- Chỉ dùng □ cho chữ thật sự không đọc được/khuyết **trong nguồn**, ở cả `han` và `phien_am`; bản dịch khuyết ghi `[...]`;
  ghi lý do ở `ghi_chu`. Không dùng `+ ? *` hay ký hiệu khác. Dòng có □/[...] không tính chỉ tiêu.
- Không thêm/bớt dòng trống; giữ thứ tự sách; `sent_id` đánh lại liên tục nếu tách/gộp dòng.

Sửa xong, đồng bộ và kiểm tra:
```powershell
.\venv\Scripts\python.exe dong_hang.py --ma-sach R1001 --sync xlsx
```
Lệnh đọc sheet `DONG_HANG`, chuẩn hóa ô (NFC, bỏ khoảng trắng/tab/xuống dòng thừa, bỏ dòng trống),
ghi lại cả TSV và XLSX giống hệt nhau rồi chạy script kiểm tra. Sửa trên TSV thì dùng `--sync tsv`.
Chỉ kiểm tra: `--check-only`.

## 6. Bước 4 — Nghiệm thu nội bộ (HD mục 6–8)
- Script kiểm tra phải báo **0 lỗi**; độ khớp âm **≥ 95%**.
- Lấy mẫu ngẫu nhiên các cặp, chấm theo 8 tiêu chí HD mục 6, phân loại OMISSION/ADDITION/MISSING;
  tỷ lệ lỗi ≤ 30% (mục tiêu ≤ 20%). Ghi vào `metadata/quality_reviews.tsv`, rồi rà lỗi tương tự toàn file.
- Ghi số cặp hợp lệ theo thành viên vào `metadata/assignments.tsv` (chỉ tiêu ≥ 2.000 cặp/người với sách scan).

## 7. Bước 5 — Đóng gói (HD mục 2, 9)
Cây `<MSSV1_MSSV2_MSSV3_MSSV4>.zip` gồm thư mục `<MA_SACH>/` (01–04), `_report.pdf` và `source.zip`
(mã nguồn + README.md + USER_GUIDE.md + requirements.txt, **không** kèm API key). Chưa có script tự đóng gói.

## 8. Lỗi thường gặp

| Hiện tượng | Nguyên nhân / cách sửa |
| --- | --- |
| `No module named 'pkg_resources'` | `pip install "setuptools<81"` |
| `03_text_sach/han.txt` toàn □ | Thiếu từ điển lúc chạy OCR. Chép từ điển vào `guideline/dict/`; `dong_hang.py` tự dùng OCR thô thay thế |
| `Không tìm thấy PDF` | Đặt PDF vào `docs-local/NLP-20261101T150232Z-1-001/NLP/` |
| `FileNotFoundError: vietocr_configs/base.yml` | Chạy lệnh từ thư mục gốc repo; xem mục 2 |
| `đã có file dóng hàng` | Đã sửa tay → `--sync xlsx`; muốn làm lại bản nháp → `--force` |

## Kiểm thử
```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests/alignment -p "test_*.py" -v
```
Có `guideline/` thì test chạy thêm phép thử tái tạo đúng 22/22 cặp trong `MAU_parallel.tsv`.

## Quy ước đường dẫn
[Cây thư mục trong README](README.md#cây-thư-mục-hiện-tại) mô tả repo thực tế.
Code thuộc src/han_viet_alignment/, không dùng src/sac_phong/ hoặc src/minh_menh/.
Tên thư mục tests/sac_phong/ và tests/minh_menh/ là đúng vì tests nhóm theo chức năng.
Không đổi tên tài liệu gốc trong docs-local để ép theo quy ước tên module.
workspace/ được tạo local khi cần; Git không lưu thư mục rỗng hoặc dữ liệu đã ignore.

## Kiểm tra trước khi mở PR
Không cần Claude, Codex hoặc Spec Kit CLI. Cần Python ≥3.11:
```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-ci.txt
.venv/bin/python scripts/check_scaffold.py
.venv/bin/python scripts/check_project.py
.venv/bin/python -m unittest discover -s tests/common -p 'test_*.py' -v
```
Windows dùng .venv/Scripts/python.exe.
Mở PR vào main, xem mục Checks và xử lý lỗi; nếu GitHub báo merge conflict,
cập nhật nhánh và giải quyết xung đột. Nhờ leader review trước khi merge.
CI hiện kiểm tra khung/cấu hình, chưa kiểm tra chất lượng pipeline OCR/dóng hàng.
Công cụ AI cá nhân của leader không phải yêu cầu cài đặt của thành viên.
