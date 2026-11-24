# Hướng dẫn sử dụng

Cách chạy từ đầu đến cuối trên máy mới. Quy tắc gốc: `guideline/HUONG_DAN_DO_AN_HAN_VIET_HANH_CHINH.pdf` (gọi tắt **HD**).
Máy chỉ tạo **bản nháp** — người phải kiểm tra lại trước khi nộp.

```text
PDF ─► ocr_tho.py ─► dong_hang.py (sắc phong)          ─► sửa tay ─► kiểm tra ─► nộp
                     dong_hang_minh_menh.py (Minh Mệnh)
```

Mọi lệnh chạy **từ thư mục gốc repo** trên PowerShell. macOS/Linux: thay `.\venv\Scripts\python.exe` bằng `venv/bin/python`.

---

## 1. Cài đặt (làm một lần)

```powershell
git clone <url-repo> han-viet-alignment
cd han-viet-alignment
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```
Môi trường đã chạy: Python 3.12.0, Windows 11 (64-bit), RAM 16 GB, chạy trên CPU (không cần GPU).
Mọi thư viện trong `requirements.txt` đã được cố định phiên bản.

Tải model OCR tiếng Việt:
```powershell
New-Item -ItemType Directory -Force vietocr_configs, models, guideline\dict, guideline\mau_du_lieu
Invoke-WebRequest https://raw.githubusercontent.com/pbcquoc/vietocr/master/config/base.yml -OutFile vietocr_configs\base.yml
Invoke-WebRequest https://raw.githubusercontent.com/pbcquoc/vietocr/master/config/vgg-transformer.yml -OutFile vietocr_configs\vgg-transformer.yml
Invoke-WebRequest https://vocr.vn/data/vietocr/vgg_transformer.pth -OutFile models\vgg_transformer.pth
```

Chép các file của giáo viên vào đúng chỗ (không commit các file này):

| File | Đặt vào |
| --- | --- |
| PDF sách (`tap 1.pdf`, …) | `docs-local/NLP-20261101T150232Z-1-001/NLP/` |
| `QuocNgu_SinoNom_TongHop3.xlsx`, `SinoNom_Similar_Dic_v2.xlsx` | `guideline/dict/` |
| `kiem_tra_du_lieu.py`, `MAU_parallel.tsv/.xlsx` | `guideline/mau_du_lieu/` |

> **Phải có từ điển trước khi chạy OCR**, nếu không chữ Hán không được sửa và không tính được độ khớp âm.

---

## 2. OCR

Chạy thử vài trang, xem ảnh trong `R1001/02_ocr_tho/`, ổn rồi mới chạy cả sách:
```powershell
.\venv\Scripts\python.exe ocr_tho.py --pdf "tap 1.pdf" --pages 4-7   --ma-sach R1001
.\venv\Scripts\python.exe ocr_tho.py --pdf "tap 1.pdf" --pages 4-178 --ma-sach R1001
.\venv\Scripts\python.exe ocr_tho.py --pdf "tap 3.pdf" --pages 5-252 --ma-sach R1003
```
- Log phải có `mô hình Paddle v6` (nếu thấy `RapidOCR mặc định` là tải model lỗi).
- Chạy lại dùng cache; thêm `--force` để OCR lại.
- Kết quả: `<MA_SACH>/02_ocr_tho/` (OCR thô, **không sửa tay**) và `<MA_SACH>/03_text_sach/`.

---

## 3. Dóng hàng

### Sắc phong (R1001, R1003)
```powershell
.\venv\Scripts\python.exe dong_hang.py --ma-sach R1001
```
Script tự làm sạch, tách câu, dóng Hán – phiên âm – dịch nghĩa, rồi **tách nhỏ đến mệnh đề** (tại `, ; :`)
khi hai vế tương ứng rõ ràng (HD 3.1: ưu tiên đơn vị nhỏ nhất). Chữ OCR sai mà không có bằng chứng để sửa thì ghi □.

Kết quả:
- `R1001/04_dong_hang/R1001_parallel.tsv` + `.xlsx` — file nộp
- `workspace/R1001/review.tsv` — danh sách dòng cần người xem

Script **không ghi đè** file đã có để khỏi mất bản sửa tay. Muốn tạo lại bản nháp từ đầu: thêm `--force`.

**File đã sửa tay nhưng còn dóng theo câu dài?** Tách nhỏ tại chỗ, giữ nguyên phần đã sửa:
```powershell
.\venv\Scripts\python.exe dong_hang.py --ma-sach R1001 --tach-menh-de
```
Tắt giao diện sửa (`tools/fix_ui`) trước khi chạy. Mỗi file chỉ chạy một lần. Bản cũ lưu ở `workspace/R1001/truoc_tach_menh_de/`.

### Minh Mệnh chính yếu (R1204, R1205, R1206 — không có phiên âm)
```powershell
.\venv\Scripts\python.exe dong_hang_minh_menh.py --ma-sach R1204 --force
```
Bản Hán không có dấu câu, nên ranh giới câu Hán được suy ra từ bản dịch. Script chỉ cắt ở những ranh giới có
độ tin cậy đủ cao. Ở ranh giới không chắc chắn, hai câu dịch liền nhau được **gộp vào một cặp (kiểu 1–n,
HD 3.1)**: gộp vẫn giữ đúng quan hệ dịch, còn cắt sai sẽ làm hỏng cả hai cặp.

Tham số `--nguong-gop` quy định độ tin cậy tối thiểu để giữ một điểm cắt. Ngưỡng càng cao thì càng gộp nhiều,
cặp ít hơn nhưng ranh giới chính xác hơn. Giá trị mặc định theo từng sách nằm trong `NGUONG_GOP` của
`dong_hang_minh_menh.py` (R1204 = 1.25, R1205 = 1.25, R1206 = 1.75). Các giá trị này được chọn trên mẫu
đánh giá ranh giới ở `docs/danh_gia_minh_menh/`:

| `--nguong-gop` | Số cặp (cả 3 sách) | Tỷ lệ cặp lệch ranh giới ước lượng |
| --- | --- | --- |
| 1.25 | ~2.240 | ~23% |
| 1.5 | ~2.000 | ~20% |
| 1.75 | ~1.750 | ~10% |

Tỷ lệ trên là **ước lượng** từ một mẫu nhỏ (141 khối / 404 ranh giới) do mô hình ngôn ngữ gán nhãn (xem mục 7),
**chưa được người chấm lại**. Trước khi nộp, phải chấm tay mẫu ngẫu nhiên theo mục 5.

Kết quả: `R1204/04_dong_hang/R1204_parallel.tsv` + `.xlsx` và `workspace/R1204/review_minh_menh.tsv`
(xem trước các cặp có cờ `RANH_GIOI_SAT_NGUONG`).

---

## 4. Sửa tay (bắt buộc)

### Cách 1 — Giao diện web (khuyên dùng)
```powershell
.\venv\Scripts\python.exe tools\fix_ui\server.py --book R1001
```
Mở `http://127.0.0.1:8765`. Màn hình có 3 cột: từ điển · câu đang sửa · ảnh gốc.
- **Phiên âm & Dịch nghĩa**: sửa trong ô, rời ô là lưu. `Ctrl+Enter` = lưu + duyệt + câu sau.
- **Chữ Hán**: chọn một ô chữ → bấm chữ đúng ở cột trái (hoặc phím `1`–`9`). `Backspace` = □, `N` = tới ô □ kế tiếp, `V` = duyệt câu.

Sửa xong, đồng bộ sang xlsx:
```powershell
.\venv\Scripts\python.exe dong_hang.py --ma-sach R1001 --sync tsv
```

### Cách 2 — Sửa file Excel
Mở `R1001/04_dong_hang/R1001_parallel.xlsx`, sửa, lưu, rồi chạy:
```powershell
.\venv\Scripts\python.exe dong_hang.py --ma-sach R1001 --sync xlsx
```
**Không dùng cả hai cách cùng lúc** (bên này sẽ ghi đè bên kia).

### Cần sửa gì
Xem cột `canh_bao` trong `workspace/<MA_SACH>/review.tsv`, đối chiếu ảnh gốc trong `02_ocr_tho/`:

| Cờ | Cách sửa |
| --- | --- |
| `LECH_SO_CHU(a/b)` | Số chữ Hán ≠ số âm tiết: thêm/bớt chữ theo ảnh |
| `KHOP_AM_DUOI_95` | Có chữ không khớp âm (xem cột `chu_lech`): sửa chữ theo ảnh |
| `CHE_CHU_SAI`, `OCR_THIEU_CHU`, `THIEU_HAN`, `PA_THIEU_AM` | Có □: nhập chữ đúng từ ảnh |
| `SUA_HAN`, `SUA_PA` | Máy đã tự sửa: xác nhận lại theo ảnh |
| `GIAN_THE` | Chữ giản thể do OCR: sửa về chữ phồn thể **theo ảnh** |
| `THIEU_DICH` | Thiếu bản dịch: nhập bản dịch **của sách** (không tự dịch, không dùng AI) |
| `LECH_MOC_*`, `LECH_DO_DAI`, `THIEU_TEN_RIENG` | Cặp có thể lệch câu: kiểm tra ranh giới |

Quy tắc chính (HD mục 3):
- Cột `han` viết liền, giữ phồn thể/dị thể; số chữ Hán = số âm tiết phiên âm.
- Chữ không đọc được ghi □ ở cả `han` và `phien_am`; bản dịch khuyết ghi `[...]`; ghi lý do ở `ghi_chu`.
- Giữ thứ tự sách, không thêm dòng trống.

---

## 5. Kiểm tra và nộp

```powershell
.\venv\Scripts\python.exe dong_hang.py --ma-sach R1001 --check-only
```
Yêu cầu:
- Script kiểm tra báo **0 lỗi**; độ khớp âm **≥ 95%** (không áp dụng cho Minh Mệnh).
- Chấm tay một mẫu ngẫu nhiên theo 8 tiêu chí HD mục 6: tỷ lệ cặp lỗi **≤ 30%** (nên ≤ 20%).
  Ghi vào `metadata/quality_reviews.tsv`.

Nộp file `<MSSV1_MSSV2_MSSV3_MSSV4>.zip` gồm các thư mục `<MA_SACH>/` (01–04), `_report.pdf`
và `source.zip` (mã nguồn + README.md + USER_GUIDE.md + requirements.txt, **không** kèm API key).

Trang mục lục và trang xuất bản không có bản Hán tương ứng nên không đưa vào dóng hàng. Danh sách các khối OCR
bị loại và lý do nằm trong `<MA_SACH>/summary.json` (trường `excluded_docs`; vd R1001.254–257).

---

## 6. Lỗi thường gặp

| Hiện tượng | Cách sửa |
| --- | --- |
| `No module named 'pkg_resources'` | `pip install "setuptools<81"` |
| `han.txt` toàn □ | Thiếu từ điển lúc OCR: chép vào `guideline/dict/` rồi chạy lại |
| `Không tìm thấy PDF` | Đặt PDF vào `docs-local/NLP-20261101T150232Z-1-001/NLP/` |
| `FileNotFoundError: vietocr_configs/base.yml` | Chạy lệnh từ thư mục gốc repo; làm lại mục 1 |
| `đã có file dóng hàng` | Đã sửa tay → `--sync xlsx`; muốn làm lại từ đầu → `--force` (mất bản sửa tay) |

---

## 7. Mô hình ngôn ngữ / công cụ trả phí đã dùng

Theo quy định chung (phần Quy định về mã nguồn), mọi công cụ hoặc mô hình có tính phí phải được ghi rõ mô hình,
prompt và cách cài đặt. Pipeline OCR và dóng hàng ở các mục 2–3 **không** gọi dịch vụ trả phí nào. Mô hình
ngôn ngữ chỉ được dùng ở hai việc dưới đây và **không dùng để dịch, dịch bù hay viết lại bản dịch** (HD mục 1).

| Việc | Mô hình / công cụ | Đầu vào → đầu ra | Prompt |
| --- | --- | --- | --- |
| Gán nhãn ranh giới đúng cho mẫu đánh giá Minh Mệnh (dùng để chọn `--nguong-gop`) | Claude (Anthropic) <!-- TODO: ghi phiên bản mô hình đã dùng --> | `docs/danh_gia_minh_menh/*.md` → `*.labels.json` | <!-- TODO: dán nguyên văn prompt đã dùng --> |
| Hỗ trợ viết code và hiệu đính dữ liệu sắc phong R1001/R1003: đối chiếu ảnh trang sách để điền câu niên đại OCR bỏ sót, chép lại phiên âm và dịch nghĩa **đúng như sách in** cho các văn bản OCR hỏng nặng (R1001.032, R1001.253, R1003.139, .175, .231, .260, .394) rồi dóng lại | Claude Opus 5.5 qua Claude Code (CLI) | Ảnh trong `02_ocr_tho/viet/` và `cache_pages/` → TSV `04_dong_hang/` | Yêu cầu bằng lời: sửa theo nhận xét của người duyệt, đối chiếu ảnh trang sách |

Cài đặt Claude Code: `npm install -g @anthropic-ai/claude-code`, rồi chạy `claude` và đăng nhập bằng tài khoản
Anthropic. Không lưu API key trong repo.

---

## Dành cho người phát triển

Chạy test:
```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests/alignment -p "test_*.py"
.\venv\Scripts\python.exe -m unittest tests.minh_menh.test_minh_menh
```

Trước khi mở PR:
```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-ci.txt
.\venv\Scripts\python.exe scripts/check_scaffold.py
.\venv\Scripts\python.exe scripts/check_project.py
.\venv\Scripts\python.exe -m unittest discover -s tests/common -p "test_*.py"
```
Mở PR vào `main`, xem tab Checks, nhờ leader review trước khi merge.
Code nằm trong `src/han_viet_alignment/`; cách thuật toán chạy được ghi trong docstring đầu mỗi file.
