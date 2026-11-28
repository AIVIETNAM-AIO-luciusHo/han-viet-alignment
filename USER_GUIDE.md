# Hướng dẫn sử dụng

Cách chạy từ đầu đến cuối trên máy mới. Quy tắc gốc: `guideline/HUONG_DAN_DO_AN_HAN_VIET_HANH_CHINH.pdf` (gọi tắt **HD**).
Máy chỉ tạo **bản nháp** — người phải kiểm tra lại trước khi nộp.

```text
PDF ─► ocr_tho.py ─► dong_hang.py (sắc phong)          ─► sửa tay ─► kiểm tra ─► nộp
                     dong_hang_minh_menh.py (Minh Mệnh)
text song ngữ có sẵn ─► dong_hang_song_ngu.py (Tư trị thông giám, …)
```

Mọi lệnh chạy **từ thư mục gốc repo** trên PowerShell. macOS/Linux: thay `.\venv\Scripts\python.exe` bằng `venv/bin/python`.

---

## 1. Cài đặt (làm một lần)

```powershell
cd D:\NMXLNNTN\han-viet-alignment
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```
Cần Python ≥ 3.11.

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
Chữ Hán không có dấu câu nên máy chỉ cắt ở chỗ chắc chắn; chỗ không chắc thì **gộp 2 câu dịch vào một cặp**
(gộp vẫn đúng nghĩa, cắt sai thì hỏng cả hai cặp). Mức gộp chỉnh bằng `--nguong-gop`:

| `--nguong-gop` | Số cặp (cả 3 sách) | Lỗi ước lượng |
| --- | --- | --- |
| 1.0 | ~2.540 | ~30% |
| 1.25 | ~2.240 | ~23% |
| 1.5 | ~2.000 | ~20% |
| 1.75 | ~1.750 | ~10% |

Mặc định: R1204 = 1.25, R1205 = 1.25, R1206 = 1.75. Số cao hơn → ít cặp hơn nhưng ít lỗi hơn.
Lỗi ước lượng tính trên mẫu nhỏ do mô hình AI chấm (`docs/danh_gia_minh_menh/`), **vẫn phải chấm tay** (mục 5).

Kết quả: `R1204/04_dong_hang/R1204_parallel.tsv` + `.xlsx` và `workspace/R1204/review_minh_menh.tsv`
(xem trước các cặp có cờ `RANH_GIOI_SAT_NGUONG`).

### Text song ngữ đã có sẵn (vd Tư trị thông giám R13128–R13130 — không phiên âm)
Dùng khi đã có **hai file text sạch**: một file chữ Hán, một file bản dịch, **mỗi dòng (không rỗng) là một đoạn**
và đoạn bên Hán đi theo đúng thứ tự đoạn bên Việt (dòng trống giữa các đoạn không sao).
Đặt 2 file vào **một thư mục con bất kỳ** của thư mục sách; tên file phải có `han` và `viet` (hoặc `dich_nghia`):
```text
R13128/
└── data/                 ← tên thư mục con tùy ý
    ├── 128.han.txt
    └── 128.viet.txt
```
Script tự tìm, chép sang `R13128/03_text_sach/han.txt` + `dich_nghia.txt` (theo hợp đồng dữ liệu) rồi dóng hàng.
Muốn chỉ rõ file thì dùng `--han` / `--viet`.
```powershell
.\venv\Scripts\python.exe dong_hang_song_ngu.py --ma-sach R13128
.\venv\Scripts\python.exe dong_hang_song_ngu.py --ma-sach R13128 --force      # chạy lại (mất bản sửa tay)
.\venv\Scripts\python.exe dong_hang_song_ngu.py --ma-sach R13128 --sync xlsx  # sau khi sửa tay file Excel
```
Script dóng đoạn ↔ đoạn rồi câu ↔ câu (cắt câu tại `。！？` / `. ! ?`). Mốc khớp là âm Hán-Việt của tên người,
địa danh, chức quan, can chi, tra trong từ điển `guideline/dict/`. Dòng tiêu đề dính Hán + Việt trong bản dịch
(`二年Năm Hiếu Kiến thứ 2`) được tách thành một cặp riêng. Mỗi nhóm đoạn là một `doc_id`.

Kết quả: `R13128/04_dong_hang/R13128_parallel.tsv` + `.xlsx` và `workspace/R13128/review_song_ngu.tsv`
(cột `kieu` = số câu Hán : số câu Việt; cờ `KHONG_MOC`, `LECH_DO_DAI`, `GOP_a:b` để xem trước).

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
