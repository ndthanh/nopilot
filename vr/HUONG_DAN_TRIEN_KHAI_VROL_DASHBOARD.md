# Hướng dẫn triển khai VROL v9.2.0 + RPA Ops Dashboard v0.14.0

Tài liệu này dùng cho lần triển khai production **bắt đầu từ đầu (reset)**: không mang
`reviewed_guids.txt`, review holds hay lịch sử run của bản cũ sang.

## 1. Tổng quan

| Thành phần | Vai trò |
|---|---|
| **VROL** (`vrol-v9.2.0-rc2.zip`) | Đăng nhập Visa Online, ROL500 preflight, tra cứu giao dịch, tải PI, tạo case + điền questionnaire, (tuỳ config) Final Submit, ghi kết quả vào file 09 |
| **RPA Ops Dashboard** (`rpa_ops-dashboard-v0.14.0.zip`) | Ghép input FC + GUID2PAN thành bundle cho VROL, cho chọn file thủ công, khởi chạy VROL, theo dõi run trực quan |

Hai bên nói chuyện qua file, không qua HTTP:

- **Input** (dashboard → VROL): bundle `<VROL>\runtime\ops_inputs\<bundle_id>\manifest.json`
  (schema `vrol-input/1`) chứa bản sao cố định của `09_chargeback_classified.xlsx` và `input.txt` (GUID|PAN).
- **Trạng thái** (VROL → dashboard): mỗi run ghi `<VROL>\runtime\async_parallel\<run_id>\dashboard_status.json`
  (schema `vrol-dashboard/2`), cập nhật mỗi 5 giây.
- **Trạng thái nghiệp vụ lâu dài**: cột **AK/AL/AM** của file 09 + ledger `runtime\business_state.sqlite3`.
  Không còn `reviewed_guids.txt` hay thư mục `runtime\review_holds`.

## 2. Yêu cầu máy

- Windows 64-bit, Python 3.12+ 64-bit (`py -3`), Google Chrome bản ổn định.
- Chạy trong phiên Windows **đã đăng nhập** (Task Scheduler: *Run only when user is logged on*).
- Đặt cả hai project **ngoài OneDrive** (ví dụ `D:\Bots\...`): OneDrive khoá file khi đồng bộ làm hỏng ghi Excel/SQLite.
- Tham khảo tài nguyên đã đo khi chạy 9 worker: CPU đỉnh ~18 %, RAM đỉnh ~53 %, Chrome ~5,7 GB.

## 3. Cài VROL

```bat
rem 1. Giải nén vrol-v9.2.0-rc2.zip vào D:\Bots\VROL, mở CMD tại thư mục đó
cd /d D:\Bots\VROL
install.cmd

rem 2. Tạo config.xlsx từ mẫu và đặt đường dẫn (OTP, 9 worker)
configure_paths.cmd --otp-dir "D:\Secrets\VisaOTP" --workers 9
```

`configure_paths.cmd` tạo `config.xlsx` từ `config.sample.xlsx` (nếu chưa có), sao lưu
`config.before_paths.xlsx`, rồi ghi các đường dẫn. Sau đó mở `config.xlsx`:

1. Sheet **Settings**: điền `username`, `password` Visa Online.
2. Sheet **SecurityQuestions**: điền câu hỏi/đáp án bảo mật (cột Enabled = YES).
3. Kiểm tra các key ở mục 7.

Nếu muốn dùng lại phiên đăng nhập đã tin cậy của máy cũ (đỡ hỏi OTP), copy thư mục
`browser_profile` của bản cũ vào `D:\Bots\VROL\browser_profile` **khi cả hai bot đều đang tắt**.

Lần đầu chạy thử an toàn (3 GUID, chỉ đọc + tải PI, không tạo case):

```bat
run_async_native_test.cmd
```

Nếu Visa hỏi OTP: tạo file `YYYYMMDD_HHMMSS_<8 số OTP>.txt` trong thư mục `otp_folder_path`.

Kiểm tra offline (không mở Visa): `run_offline_tests.cmd`.

## 4. Cài Dashboard

```bat
rem 1. Giải nén rpa_ops-dashboard-v0.14.0.zip vào D:\Apps\RPAOps, mở CMD tại đó
cd /d D:\Apps\RPAOps
install.cmd

rem 2. Trỏ dashboard tới các bot (đổi đường dẫn cho đúng máy)
configure_paths.cmd --non-interactive --visa-root "D:\Bots\VROL" --fc-root "D:\Bots\FC" --guid2pan-root "D:\Bots\GUID2PAN" --reports-dir "D:\RPAReports"

rem 3. Chạy
run_server.cmd
```

Mở **http://127.0.0.1:8765/#/bot/vrol_master**. Tự khởi động khi đăng nhập Windows: `install_startup_task.cmd`.

Thiết lập trong trang **Thiết lập** (lưu ở `data\rpa_ops.db`):

| Setting | Mặc định | Ý nghĩa |
|---|---|---|
| SERVER_HOST / SERVER_PORT | 127.0.0.1 / 8765 | Đổi cần restart. Giữ localhost nếu chưa có kiểm soát truy cập |
| CRAWL_INTERVAL_MINUTES | 2 | Chu kỳ collect + xuất bundle FC/GUID2PAN |
| VROL_GUID_POLL_SECONDS | 5 | Chu kỳ cập nhật màn hình theo dõi VROL |
| VROL_INPUT_CONTRACT_DIR | trống = `<VROL>\runtime\ops_inputs` | Phải khớp `scheduled_contract_dir` của VROL nếu đổi |
| STATIC_REPORT_ENABLED / OUTPUT_DIR | | Báo cáo tĩnh; tắt hoặc trỏ tới ổ có thật |

Root của VROL cũng đổi được ở **Thiết lập → Bots → VROL Visa**.

## 5. Luồng 1 – Chạy tự động theo lịch 19:40 (luồng chính)

Đây là luồng vận hành hằng ngày. Chạy tay trên dashboard (mục 6) chỉ là luồng bổ sung; hai luồng
dùng chung một khoá (`runtime\vrol_process.lock`) nên không bao giờ chạy chồng lên nhau.

### 5.1. Dòng thời gian mỗi tối

| Giờ | Việc | Ai làm |
|---|---|---|
| từ 19:30 | FC (Phân loại Fraud) rồi GUID2PAN chạy xong trong ngày | Task Scheduler của 2 bot upstream |
| ≤ 2 phút sau khi cả hai xong | Dashboard ghép cặp FC + GUID2PAN, kiểm tra GUID↔PAN, xuất bundle READY vào `<VROL>\runtime\ops_inputs\<bundle_id>\manifest.json` | **Collector của dashboard** (mỗi `CRAWL_INTERVAL_MINUTES` = 2) |
| 19:40 | Task Scheduler gọi **`run_scheduled.cmd`** | Task Scheduler |
| 19:40 → tối đa 20:10 | VROL chờ bundle READY của hôm nay (kiểm tra mỗi 10 giây), **chưa mở Chrome**; dashboard hiện bước *Chờ input FC + GUID2PAN* và lý do | VROL |
| khi có bundle | Đăng nhập Visa → ROL500 preflight → xử lý GUID → ROL500 postflight → ghi AK/AL/AM | VROL |

> **Quan trọng:** bundle cho luồng lịch **chỉ do dashboard tạo**. Dashboard (`run_server.cmd`) phải đang chạy
> lúc upstream hoàn tất – cài `install_startup_task.cmd` để server tự chạy khi đăng nhập Windows.
> Dashboard tắt ⇒ không có bundle ⇒ VROL chờ hết 30 phút rồi dừng với `SCHEDULED_INPUT_TIMEOUT`.

### 5.2. Hẹn giờ trong Task Scheduler

Gọi **`run_scheduled.cmd`** (không dùng `run_vrol_from_ops.cmd` hay các file `run_async_*_test.cmd` cho lịch).

| Mục | Giá trị |
|---|---|
| Name | `\RPA Tra Soat\VROL 19h40` |
| Trigger | Daily, **19:40** |
| Action → Program/script | `C:\Windows\System32\cmd.exe` |
| Action → Add arguments | `/d /c ""D:\Bots\VROL\run_scheduled.cmd""` |
| Action → Start in | `D:\Bots\VROL` (không có dấu nháy) |
| General | **Run only when user is logged on** (Chrome + thư mục OTP cần phiên người dùng); không cần *highest privileges* |
| Settings | *If the task is already running*: **Do not start a new instance**; không đặt *Stop the task if it runs longer than* ngắn (run 1.200 GUID mất ~90 phút) và không bật tự restart khi lỗi |
| Conditions | Bỏ chọn *Start only if on AC power*; máy không được Sleep/Log off lúc 19:30–22:00 |

Tạo nhanh bằng lệnh (CMD, đổi đường dẫn):

```bat
schtasks /Create /F /TN "\RPA Tra Soat\VROL 19h40" /SC DAILY /ST 19:40 /IT /RL LIMITED /TR "cmd.exe /d /c \"D:\Bots\VROL\run_scheduled.cmd\""
```

Sau khi tạo, mở Task Scheduler đặt *Start in* = `D:\Bots\VROL` và *Do not start a new instance*, rồi bấm **Run** một lần
khi `allow_final_submit = NO` để kiểm tra (nếu chưa có bundle hôm nay, run sẽ chờ rồi báo `SCHEDULED_INPUT_TIMEOUT` – đúng thiết kế).

### 5.3. Thiết lập mặc định của luồng lịch

| Thiết lập | Mặc định | Nằm ở |
|---|---|---|
| Chế độ chạy | **Luôn đầy đủ** (ô *Chế độ chạy* trên dashboard không áp dụng cho lịch) | `run_scheduled.cmd` |
| Final Submit | thiết lập dashboard nếu có, nếu không theo `allow_final_submit` (mẫu = `NO`) | Dashboard › Thiết lập chạy VROL / `config.xlsx` › Settings |
| Số worker | thiết lập dashboard nếu có, nếu không `async_worker_count` (giới hạn bởi `async_worker_max`); `configure_paths.cmd --workers 9` đặt cả hai = 9 | Dashboard / `config.xlsx` › Settings |
| Headless / headful | thiết lập dashboard nếu có, nếu không `headless` (mẫu = `False`, có cửa sổ Chrome) | Dashboard / `config.xlsx` › Settings |
| Restart Chrome | mỗi `async_restart_after_guids` = 100 GUID | `config.xlsx` › Settings |
| Thư mục chờ bundle | `scheduled_contract_dir` = `runtime\ops_inputs` (tương đối theo thư mục VROL) | `config.xlsx`; phải khớp `VROL_INPUT_CONTRACT_DIR` của dashboard |
| Giờ cắt input | `scheduled_source_not_before` = `19:30`: FC **và** GUID2PAN phải hoàn tất trong ngày, sau giờ này | `config.xlsx` |
| Thời gian chờ tối đa | `scheduled_input_wait_seconds` = 1800 (30 phút) | `config.xlsx` |
| Chu kỳ kiểm tra | `scheduled_input_poll_seconds` = 10 | `config.xlsx` |
| ROL500 trước/sau | `rol500_preflight_enabled` / `rol500_postflight_enabled` = YES | `config.xlsx` |
| Chu kỳ dashboard xuất bundle | `CRAWL_INTERVAL_MINUTES` = 2 | Dashboard › Thiết lập |

Bundle được luồng lịch chấp nhận khi: `status = READY`, `business_date` = hôm nay, có thời điểm hoàn tất của cả FC
và GUID2PAN nằm trong khoảng [giờ cắt, hiện tại], và hash 2 file khớp. Nếu có nhiều bundle, chọn bundle mới nhất.
Bundle *file tự chọn* (`manual_…`) **không bao giờ** được luồng lịch dùng.

### 5.4. Khi luồng lịch không chạy được

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `SCHEDULED_INPUT_TIMEOUT: WAITING_TODAY_READY_FC_GUID2PAN_AFTER_19:30` | Upstream xong sau 20:10, upstream lỗi, hoặc dashboard không chạy | Khi upstream xong: dashboard › chọn *Input dùng để chạy lại* → **Chạy với input mới nhất hôm nay** |
| Upstream đã chạy xong trước 19:30 (chạy sớm/chạy lại) nhưng lịch không nhận | Giờ hoàn tất trước giờ cắt | Chạy tay từ dashboard, hoặc hạ `scheduled_source_not_before` |
| `VROL_ALREADY_RUNNING` | Đang có run tay từ dashboard | Đợi run đó xong; chạy lại tay nếu cần |
| Dashboard báo *Chưa thể giao input VROL: …* | Cặp FC/GUID2PAN không hợp lệ (thiếu PAN, file đổi sau khi chạy…) | Xem thông điệp ở ô Input của dashboard, sửa upstream |

Mã thoát `run_scheduled.cmd`: `0` = hoàn tất (kể cả còn GUID cần review), `2` = ROL500 postflight lỗi, `1` = lỗi khác
(ví dụ hết thời gian chờ input). Task Scheduler hiển thị ở cột *Last Run Result*.

## 6. Luồng 2 – Chạy tay từ dashboard và theo dõi

**Chế độ chạy VROL** (ô chọn phía trên, áp dụng cho cả ba cách khởi chạy):

| Chế độ | Bot làm gì | Ghi AM |
|---|---|---|
| **Đầy đủ** (mặc định) | Tra cứu, tải PI, tạo case + điền questionnaire; Final Submit theo `allow_final_submit` | Mọi kết quả |
| **Chỉ tải chứng từ (PI = Yes)** | Tra cứu mọi GUID, tải PI cho giao dịch có cột *Eligible for Purchase Inquiry* = Yes; **không** bấm Issuer Action, không tạo case | `PI`, `NO_CB`, `Assoc D`, `Đã CB`; GUID cần tạo case để trống AM để run đầy đủ sau xử lý (trên dashboard: ô *Cần tạo case (chạy đầy đủ)*) |

Chạy tay ngoài dashboard: `set RPA_OPS_RUN_MODE=PI_ONLY` trước `run_vrol_from_ops.cmd <manifest>` (tương đương `--pi-only --write-master`).

Có ba cách khởi chạy (đều chặn nếu VROL đang chạy):

1. **Input tự động FC + GUID2PAN** – khi FC và GUID2PAN chạy xong trong ngày, dashboard xuất
   bundle READY; chọn ở ô *Input dùng để chạy lại* → **Chạy với input mới nhất hôm nay**
   (dùng khi lịch 19:40 bị lỡ hoặc cần chạy lại trong ngày).
2. **File tự chọn** – mở khối **Chạy VROL với file tự chọn (09 + input.txt)**:
   bấm **Chọn…** (mở hộp thoại Windows trên máy chạy dashboard) hoặc dán đường dẫn,
   **Kiểm tra 2 file** (header, định dạng GUID|PAN, GUID thiếu PAN), rồi **Chạy VROL với 2 file này**.
   Dashboard đóng băng bản sao vào `runtime\ops_inputs\manual_…`; kết quả AK/AL/AM ghi **vào chính file 09 đã chọn**.
3. **Chạy riêng theo GUID** – nhập danh sách GUID trên contract hôm nay.

Tab **Theo dõi run** (mặc định khi mở VROL):

- Thanh tiến độ: GUID xong/tổng, GUID/phút, thời gian còn lại; các bước (Chờ input FC + GUID2PAN với run theo lịch) → Đăng nhập → ROL500 → Xử lý GUID → Postflight → Hoàn tất.
- Chip *Chạy theo lịch (run_scheduled.cmd)* / *Chạy tay* cho biết run thuộc luồng nào.
- Ô KPI (bấm để lọc bảng): Đã tải PI · NO_CB · Đã có chargeback (ROL500 + Assoc D) · Nháp chờ Final Submit · Đã Final Submit · Cần review · Thử lại run sau.
- **Cần xử lý**: GUID cần review nhóm theo lý do, kèm hướng dẫn và nút mở thư mục/ảnh.
- **Worker**: GUID đang làm và thời gian (đỏ nếu > 3 phút); CPU/RAM/Chrome; số lần restart Chrome.
- **Case nháp chờ Final Submit**: GUID + ROL, nút **Tải CSV**.
- Cảnh báo lớn khi chờ OTP hoặc run lỗi.

Trạng thái run: `RUNNING` / `WAITING_OTP` (xanh dương/vàng), `SUCCESS` và
**`COMPLETED WITH REVIEWS`** (xanh lá: chạy xong, còn GUID trả user hoặc case nháp), `FAILED` (đỏ).

### 6.1. Thiết lập chạy VROL trên dashboard (Final Submit · số worker · headless/headful)

Khối **Thiết lập chạy VROL** (đầu khung VROL) cho đổi 3 thiết lập mà không cần mở `config.xlsx`:

| Ô | Lựa chọn |
|---|---|
| Final Submit | *Theo config.xlsx (đang: …)* · *Tắt: dừng trước Final Submit* · *BẬT: gửi Final Submit thật* |
| Số worker | *Theo config.xlsx (đang: N)* · 1 … 9 |
| Trình duyệt | *Theo config.xlsx (đang: …)* · *Headful* · *Headless* |

- Bấm **Lưu thiết lập** (có hộp xác nhận; bật Final Submit có cảnh báo riêng). Lựa chọn được **ghi nhớ** vào
  `<VROL>\runtime\run_overrides.json` và áp dụng cho **mọi run sau, kể cả lịch 19:40** (VROL tự đọc file này khi khởi động).
  Run đang chạy không bị ảnh hưởng.
- **Dùng lại config.xlsx cho cả 3** = xoá ghi đè (giá trị `null` trong file).
- Thứ tự ưu tiên trong bot: **cờ dòng lệnh > thiết lập dashboard > config.xlsx**. Vì vậy launcher chẩn đoán
  (`--pre-submit-only`, chế độ *Chỉ tải chứng từ*, `run_async_*_test.cmd`) luôn chặn Final Submit; `--workers N`, `--headless/--headful` trên dòng lệnh luôn thắng.
- Màn hình theo dõi ghi nguồn trên chip, ví dụ *Final Submit BẬT · dashboard*, *9 worker · dashboard*; log run có dòng `DASHBOARD RUN SETTINGS APPLIED`.
- Thiết lập dashboard bị bỏ qua nếu giá trị không hợp lệ (bot dùng config.xlsx).

### 6.2. Báo cáo tĩnh (thư mục báo cáo chia sẻ)

Khi `STATIC_REPORT_ENABLED = TRUE`, sau mỗi lần collect dashboard ghi vào `STATIC_REPORT_OUTPUT_DIR`:

| File | Nội dung |
|---|---|
| `index.html` | Ảnh chụp **chỉ đọc** của dashboard (cùng giao diện, kể cả tab *Theo dõi run* của VROL); các nút chạy/thiết lập tự ẩn |
| `vrol\<run_id>\index.html` | **Gói review** của run VROL hoàn tất gần nhất (run cũ vẫn giữ gói của chúng) |
| `vrol\<run_id>\guid_results.csv` | Mọi GUID: nhãn AM, nhóm, trạng thái, lý do, ROL, link ảnh |
| `vrol\<run_id>\drafts.csv` | Case nháp chờ Final Submit (GUID, ROL, Fraud/Consumer) |
| `vrol\<run_id>\existing_chargebacks.csv` | GUID bỏ qua vì đã có chargeback (ROL500 / Assoc D) |
| `vrol\<run_id>\documents\`, `groups\` | Bản sao PDF PI và ảnh bằng chứng (chỉ của run đó) |

Gói review của run mới (contract v2) gồm: luồng chạy (lịch/tay), chế độ (đầy đủ / chỉ tải chứng từ), Final Submit,
số worker, headless/headful **kèm nguồn** (dashboard / config.xlsx / lệnh chạy), thời gian, tốc độ, restart Chrome,
trạng thái ghi file 09, các bước; số GUID theo nhóm nghiệp vụ; danh sách *Cần xử lý* nhóm theo lý do kèm hướng dẫn;
case nháp; danh sách PDF; bảng tất cả GUID. Gói **không** chứa `input.txt`/PAN đầy đủ, mật khẩu hay profile Chrome.

## 7. Cấu hình VROL (`config.xlsx`, sheet **Settings**)

Sheet **Settings** là cấu hình gốc; sheet RunSettings cũ chỉ bổ sung key còn thiếu và bị bỏ qua nếu trùng. Ba key `allow_final_submit`, `async_worker_count`, `headless` có thể bị ghi đè từ dashboard (mục 6.1).

| Key | Giá trị khuyến nghị | Ý nghĩa |
|---|---|---|
| `allow_final_submit` | `NO` (mặc định) | **Công tắc Final Submit** – xem mục 8 |
| `async_worker_count` | `9` | Số worker mỗi run – xem mục 9 |
| `async_worker_max` | `9` | Trần số worker (CLI `--workers` cũng bị giới hạn bởi giá trị này) |
| `async_restart_after_guids` | `100` | Thoát Chrome, đăng nhập lại sau mỗi N GUID (chống OOM) |
| `headless` | `False` | `True` = Chrome chạy ẩn (đã diễn tập 1.212 GUID ổn định ở 9 worker) |
| `user_data_dir` | `browser_profile` | Profile Chrome giữ đăng nhập/tin cậy thiết bị |
| `otp_polling_mode` / `otp_folder_path` | `FOLDER_FILENAME` / thư mục OTP | Nơi thả file OTP |
| `classified_case_file` | đường dẫn file 09 | File 09 mặc định (khi không chạy qua bundle) |
| `guid_pan_mapping_file` | đường dẫn input.txt | Mapping GUID|PAN mặc định |
| `async_master_workbook` | trống | File 09 nhận AK/AL/AM; trống = file 09 của input (bundle thủ công: file user chọn) |
| `async_master_writeback_enabled` | `YES` | **Bắt buộc YES** cho run tạo case (bot từ chối chạy nếu NO) |
| `rol500_preflight_enabled` / `rol500_postflight_enabled` | `YES` / `YES` | Phát hiện chargeback đã có trước/sau run |
| `rol500_days_back` | `3` | Khung ngày báo cáo ROL500 |
| `scheduled_contract_dir` | `runtime\ops_inputs` | Phải khớp `VROL_INPUT_CONTRACT_DIR` của dashboard |
| `scheduled_source_not_before` | `19:30` | Run lịch tối chỉ nhận bundle hoàn tất sau giờ này |
| `business_state_retention_days` | `180` | Thời gian giữ ledger |

## 8. Bật Final Submit

1. Cách nhanh: dashboard › **Thiết lập chạy VROL** › Final Submit = **BẬT** › Lưu (mục 6.1).
   Hoặc mở `config.xlsx` → sheet **Settings** → đổi `allow_final_submit` = **YES** (lưu, đóng Excel) và để ô dashboard ở *Theo config.xlsx*.
2. Chạy bằng `run_scheduled.cmd`, `run_vrol_from_ops.cmd` hoặc từ dashboard. Các launcher này **không** có cờ chặn.
3. Các launcher chẩn đoán luôn chặn Final Submit dù config = YES: `run_async_case_test.cmd`,
   `run_async_native_test.cmd`, mọi lệnh có `--pre-submit-only`, `--pi-only`, `--inquiry-only`.

Khi bật, dashboard hiện chip đỏ **Final Submit BẬT**. Đổi công tắc **không** tự gửi các case nháp đã tạo
ở run trước (AM `FRAUD/consumer - chờ Final Submit`); muốn bot xử lý lại một GUID thì gõ `FORCE` vào AM
(bot sẽ tạo case mới, ROL mới). Muốn tắt lại: đổi về `NO`.

## 9. Số worker

- Cách nhanh: dashboard › **Thiết lập chạy VROL** › Số worker (1–9) › Lưu (mục 6.1).
- Hoặc đổi `async_worker_count` trong sheet Settings (và `async_worker_max` nếu muốn trên 5).
  Giảm worker: chỉ cần giảm `async_worker_count` (ví dụ 5). Có hiệu lực từ run kế tiếp.
- Ép tạm cho một lần chạy: thêm `--workers N` vào lệnh (bị chặn trên bởi `async_worker_max`).
- Số liệu đo (cùng 90 GUID, chỉ đọc): 5 worker 9,3 · 7 worker 11,7 · 9 worker 16,3 GUID/phút.
  Diễn tập full 9 worker headless: 14,8 GUID/phút, không lỗi kỹ thuật.
- Giảm worker nếu RAM > 85 %, CPU > 75 % kéo dài, hoặc dashboard thấy nhiều "Thử lại run sau".

## 10. Điều khiển bằng file 09 (cột AK/AL/AM)

| Cột | Bot ghi | User có thể ghi |
|---|---|---|
| **AK** (VROL) | Số ROL case (nhiều case: `ROL1 \| ROL2`) | – |
| **AL** (CB date) | Ngày bot xử lý | – |
| **AM** (CB reject) | Kết quả: `PI`, `NO_CB`, `Assoc D`, `Đã CB`, `Đã CB (reversal)`, `FRAUD - chờ Final Submit`, `consumer - chờ Final Submit`, `FRAUD`/`consumer` (đã Final Submit), `Có associated transactions`, `Nhiều dòng Sale`, `Trả user: …`, `Review: …` | `SKIP` hoặc `FORCE` |

Quy tắc: AM có giá trị bất kỳ → bot **bỏ qua cả GUID**. Ưu tiên **SKIP > FORCE > mọi nhãn khác**:
`SKIP` luôn bỏ qua; `FORCE` buộc chạy lại GUID kể cả khi đã có nhãn cũ (sau khi chạy, nhãn mới ghi đè FORCE).
Xoá trắng AM do bot ghi **không** làm bot chạy lại (báo `USER_CLEARED`); muốn chạy lại phải gõ `FORCE`.

Lưu ý: **đóng file 09 trong Excel** khi run kết thúc; nếu file đang mở, kết quả nằm trong ledger và được ghi
bù ở run sau (`master_writeback.json` = `PENDING`).

GUID có dòng còn quá mới (≤ 15 ngày): bot xử lý các dòng đủ tuổi và ghi nhãn cho cả GUID; các dòng mới hơn
sẽ không tự chạy sau đó – gõ `FORCE` khi muốn xử lý chúng.

## 11. Thư mục kết quả mỗi run

`<VROL>\runtime\async_parallel\<run_id>\`

| File/Thư mục | Nội dung |
|---|---|
| `dashboard_status.json` | Trạng thái cho dashboard (contract v2) |
| `09_CHARGEBACK_CLASSIFIED_ASYNC_REVIEW.xlsx` | Workbook kết quả kèm cột BOT … |
| `documents\` | Toàn bộ PI đã tải |
| `groups\<NHÓM>_<GUID>\` | Ảnh, PI, checkpoint, log từng GUID (`__*__.txt` là marker để lọc trong Explorer) |
| `guid_outcomes.csv`, `review_required_cases.csv` | Kết quả từng GUID, danh sách cần review |
| `existing_chargebacks.csv` | GUID bỏ qua vì đã có chargeback (ROL500 / Assoc D) |
| `console.log`, `activity_report.jsonl` | Log console, nhật ký sự kiện |
| `logs\` | `run.log`, `resources.jsonl`, `writer_metrics.jsonl` |

Phân tích hiệu năng nhiều run: `review_analyze.cmd runtime\async_parallel\<run1> runtime\async_parallel\<run2>` → `runtime\review_report.md`.

## 12. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| Dashboard báo **Đang chờ OTP Visa** | Tạo file `YYYYMMDD_HHMMSS_<OTP>.txt` trong thư mục OTP (timeout 180 s) |
| `VROL_ALREADY_RUNNING` | Một tiến trình VROL khác đang chạy (khoá `runtime\vrol_process.lock`); đợi xong |
| `MASTER_WRITEBACK_REQUIRED` | Đặt `async_master_writeback_enabled` = YES |
| `master_writeback = PENDING` | File 09 đang mở/khoá; đóng Excel, kết quả ghi bù ở run sau |
| Dashboard hiển thị run dạng cũ | Run do bản VROL cũ tạo (không có `dashboard_status.json`) |
| `WAITING_INPUT` ở run lịch tối | Chưa có bundle READY sau `scheduled_source_not_before`; kiểm tra FC/GUID2PAN |
| ROL500 preflight timeout | Visa chậm; bot tự thử lại tối đa 3 lần |
| `WINDOW_LAYOUT_NOT_STABLE` | Bot tự chờ lại 3 lần, rồi tạo lại case 1 lần (chưa Final Submit); nếu vẫn lỗi → review, gõ FORCE hoặc điền tay |
| ROL-1537 | Bot thử lại 1 lần; vẫn lỗi → trả user tra soát từng giao dịch |

Kiểm tra offline sau khi cài: `run_offline_tests.cmd` ở cả hai thư mục (không mở Visa, không gửi case).

## 13. Kiểm tra nhanh sau triển khai (không tạo case, không Final Submit)

Đã chạy thật ngày 21/11/2026: 3 GUID, tải đủ 3 PDF, ghi AM = `PI`, 219 GUID `Đã CB` từ ROL500, không có Final Submit.

1. Dashboard › **Thiết lập chạy VROL**: Final Submit = *Tắt*, Số worker = 3 › Lưu.
2. **Chế độ chạy VROL** = *Chỉ tải chứng từ (PI = Yes)*.
3. Sao chép file 09 thật ra một file thử (ví dụ `D:\Test\09_THU.xlsx`), dùng khối **Chạy VROL với file tự chọn**
   với file thử + `input.txt` › Kiểm tra 2 file › Chạy.
4. Theo dõi tab *Theo dõi run*: chip *Chỉ tải chứng từ (PI)*, *3 worker · dashboard*; kết thúc *COMPLETED WITH REVIEWS* hoặc *SUCCESS*.
5. Kiểm tra: PDF trong `runtime\async_parallel\<run_id>\documents\`, cột AM của file thử có `PI` / `Đã CB` / `Assoc D` / `NO_CB`,
   `master_writeback.json` = `UPDATED` hoặc `UNCHANGED`.
6. Trả thiết lập về **Dùng lại config.xlsx cho cả 3** (hoặc giá trị mong muốn cho production) trước 19:40.
