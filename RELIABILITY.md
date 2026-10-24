# Nâng cấp độ tin cậy — 24/10/2026

Các mục dưới đây bổ sung cho CLI và Web hiện có. Không cần dùng shell ngoài CMD/Python. Bộ challenge vẫn đạt2/5 và phiên cũ giữ60/60. Kiểm thử UI/bridge thật dùng conversation riêng:2phản hồi chat và16/20lượt explorer; không tự cấp thêm lượt.

| Mục | Đã triển khai | Giới hạn / khó khăn |
|---|---|---|
| Lưu và khôi phục phiên | State atomic, checkpoint đầy đủ và checkpoint tóm tắt sau mỗi bước; khôi phục kèm notes, projects, kết quả gần đây và schema | Browser DOM không sống qua restart. Cần review bước đang dở; không tự chạy lại. Nếu state mới hỏng/mất, dùng checkpoint nhưng coi ngân sách cũ đã hết để tránh gọi vượt lượt |
| Giao thức dữ liệu | Chặn key trùng, NaN/Infinity, sai kiểu, action/key lạ; kiểm tra cả batch và vòng lặp con trước thao tác đầu | Đây vẫn là giao thức JSON qua chat, không có system-role/function calling thật. Runtime errors sau một hành động hợp lệ có thể để lại tác động một phần |
| Ảnh/OCR | Tool gửi1–3ảnh trong một contact sheet, có mã hash in trên từng ảnh; ghi OCR bằng đúng image_id, gắn lại tên và SHA256 ở backend | Không suy tên file theo thứ tự. Đã kiểm thử qua UI với Copilot thật:2ảnh mẫu,8trường OCR đúng khi đối chiếu ảnh; không suy rộng thành độ chính xác OCR tổng quát. OCR là nội dung model đọc, không mặc định được coi là đúng |
| Phát hiện không tiến triển | Tạm dừng sau3lần cùng mutation và trạng thái quan sát, hoặc3tool lỗi liên tiếp; UI hiển thị lý do, thao tác và checkpoint | So sánh trạng thái nhìn thấy, có thể bỏ sót thay đổi backend hoặc nhầm tác vụ cố ý lặp. Read-only snapshot không tự gây pause. Resume reset bộ đếm, không cấp lượt |
| Chẩn đoán browser | diagnostics(), console warning/error, pageerror, request failed, HTTP>=400 và request bị guard chặn; tối đa100events | Không lưu headers/body; bỏ query string trong URL. Diagnostics là bằng chứng, không tự quyết định nới origin |
| Xuất project | Bỏ action chỉ đọc khỏi replay, kiểm tra success hiện tại và chạy lại trên browser mới; ZIP có replay-verification.json và ảnh khi PASS | Selector động/trace khám phá lỗi vẫn có thể làm replay thất bại. Giữ ZIP nhưng ghi FAILED/UNVERIFIED, không tự xóa thử nghiệm có thể là tiền đề. Replay giới hạn120giây giữa các action; một action đang chờ chịu timeout riêng |
| Cách ly chạy code | Có mode container tùy chọn: Linux, network none, project read-only, non-root, bỏ capabilities, giới hạn process/RAM/CPU, tmpfs; image pin bằng digest và dọn container sau chạy | Docker engine máy này không chạy nên chưa kiểm chứng cách ly end-to-end. Preflight từ chối, không fallback sang host. Container hiện chỉ trả log; chưa export file, cài deps hoặc chạy Edge |

## Dùng trong Web

Khởi động lại backend sau khi thay mã, rồi reload trang. Dev workspace hiển thị checkpoint, thao tác gần đây, lý do tạm dừng và số project replay đã kiểm chứng. Khi đang tạm dừng do lặp, xem lý do/diagnostics, gửi yêu cầu iterate để đổi chiến lược hoặc tiếp tục nếu đã xác minh việc lặp là cần thiết.

Trong phần đề xuất chạy Python, chọn **Môi trường chạy**. Mode Windows hiện tại vẫn cần duyệt từng lệnh và có quyền tài khoản Windows. Mode container không dùng được nếu Docker Linux engine hoặc image chưa sẵn sàng; lỗi preflight xuất hiện trước khi tạo phiếu duyệt. Model không có quyền tự phê duyệt hoặc đổi mode của phiếu đã lập. Các đề xuất tự động từ model hiện vẫn là host mode và phải được người dùng review; muốn container, lập đề xuất riêng từ UI hoặc CLI.

Khi backend restart, explorer hiện **Cần khôi phục có kiểm tra**. Mã, artifacts, trace và ngân sách được giữ; DOM được mở mới sau xác nhận. Không tự nối lại một prompt có trạng thái hoàn tất chưa rõ.

## Tool ảnh và chẩn đoán

```json
{"type":"tool_call","run_id":"RUN_ID","id":"images_1","tool":"browser.attach_images","arguments":{"names":["1.jpg","2.jpg"]}}
```

Backend gắn một ảnh PNG có nhãn `IMAGE <image_id> | filename`. Tool result trả `batch_id`, `image_id` và SHA256. Copilot phải đọc nhãn trực tiếp, rồi trả một record mỗi ảnh:

```json
{"type":"tool_call","run_id":"RUN_ID","id":"ocr_1","tool":"browser.record_images","arguments":{"batch_id":"BATCH_ID","records":[{"image_id":"ID_1","fields":{"InvoiceNo":"11577","TotalDue":"17310.00"}},{"image_id":"ID_2","fields":{"InvoiceNo":null,"TotalDue":null}}]}}
```

Không đoán giá trị không đọc được. Mapping foreign/missing/duplicate ID bị từ chối. `ocr-<batch>.json` lưu cả SHA256 và provenance; `verified:false` nhắc rằng cần kiểm tra nội dung trước khi submit.

```json
{"type":"tool_call","run_id":"RUN_ID","id":"diag_1","tool":"playwright","arguments":{"actions":[{"action":"diagnostics"}]}}
```

## Container từ CMD

Chuẩn bị Docker Desktop Linux engine và image do người dùng chọn. Ví dụ image mặc định cho Python standard library:

```bat
docker pull python:3.14-slim
nopilot.cmd dev --data-dir "C:\work\dev-data" run PROJECT_ID run.py --execution-mode container --timeout 120
```

Preflight chỉ kiểm tra image đã có, không tự pull. Phiếu duyệt ghi image SHA256 và đầy đủ lệnh Docker. Sau duyệt mới chạy, không mount profile/credentials/Docker socket. Source ở `/workspace` chỉ đọc; cwd `/tmp` chỉ ghi tạm. Nếu cần thư viện khác hoặc browser, phải chuẩn bị image và triển khai chính sách riêng; bản này chưa hỗ trợ chọn custom image qua UI.

## Kiểm thử lặp lại

```bat
.venv\Scripts\python.exe -m pip install -r requirements-browser.txt
.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Test browser dùng Edge thật và HTTP fixture tạm ở localhost; override URL guard chỉ trong test, không thay policy production. Test state/model dùng harness giả để không tiêu tốn lượt Copilot. Test container có kiểm tra lệnh/chính sách và từ chối engine unavailable; không coi đó là bằng chứng container đã chạy thành công.

## Kết quả UI thật

Xem [UI_TESTING.md](UI_TESTING.md) để chạy lại từ giao diện. Đã xác nhận chat tiếng Việt, upload path, Copilot đọc file và trảZIP, inspect/extract/read, từ chối duyệt không chạy, native ảnh/OCR, memory sau restart, diagnostics, fresh replay và auto-pause14/20 rồi iterate kết thúc16/20. Lượt đầu model từ chối external tools, schema repair phục hồi; prompt đã làm rõ vai trò JSON planner, chưa có đánh giá nhiều phiên mới. Docker unavailable được kiểm tra từ UI và không tạo phiếu/run thay thế.
