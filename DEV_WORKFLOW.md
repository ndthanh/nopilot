# Dev và Playwright explorer trong nopilot

Bản này đã triển khai Web và CLI workflow trên Windows bằng CMD/Python.

## Luồng sử dụng

1. Web: chọn Playwright tool, nhập URL và nhiệm vụ, hoặc dùng `/browse URL nhiệm vụ`. Mặc định 20 lượt model.
2. Copilot khám phá bằng tool JSON; mỗi lần một object có `run_id`, `id`, `tool`, `arguments`. Kết quả được trả vào chat. Đây là instruction message trong chat, không phải system role thật của Microsoft.
3. `export_project` tạo ZIP Python Playwright và nhập workspace local. ZIP tải từ Copilot cũng có nút **Xem ZIP** để inspect/extract.
4. **Dev workspace** cho đọc/sửa file, checkpoint/diff/rollback, xuất ZIP và mở folder.
5. `project.propose_run` tạo approval, chưa chạy gì. Người dùng xem source/requirements, lệnh, cwd, revision, timeout, tick đã kiểm tra rồi duyệt một lần. Dependency install cần duyệt riêng.
6. Runner chạy bản sao source đã duyệt trong venv dự án, stream stdout/stderr; có Stop toàn bộ cây process. Log giới hạn được trả lại Copilot nếu run thuộc explorer; approval card cho biết điều này.
7. Copilot sửa tiếp bằng project.write, tạo checkpoint/diff rồi xin duyệt mới. Sau final, gửi yêu cầu iterate trong Dev panel để dùng tiếp browser/workspace.
8. Đủ 20 lượt thì dừng, giữ browser. Chỉ người dùng mới cấp thêm tối đa 20 lượt mỗi lần. Close browser giữ project/artifacts.

## Giao thức mẫu

```json
{"type":"tool_call","run_id":"SESSION_ID","id":"run_1","tool":"project.propose_run","arguments":{"project_id":"PROJECT_ID","revision":"CURRENT_REVISION","kind":"run","entrypoint":"run.py","arguments":[],"timeout":120}}
```

Schema đầy đủ ở explorer.py và playwright_tool.py. Không có tool approve/execute/grant. `approved:true` không thể tạo quyền chạy. Model không chọn executable hoặc shell: backend chọn Python venv và argv. `project.write` nhận toàn bộ text từng file, tối đa 30 file/1 MiB cho một lần sửa; content:null xóa file.

## Lưu trữ và khôi phục

```text
<web-data>/conversations/<id>/
  dev/projects/<project-id>/
    source/                       # mã có thể sửa
    checkpoints/<id>/files/        # bản sao + manifest
    approved-sources/<approval-id>/ # source snapshot của từng run
    venv/                         # dependency dự án
  dev/approvals/<id>.json
  artifacts/runs/<run-id>/         # metadata, stdout, stderr, combined, outputs
  artifacts/explorers/<task-id>/   # state, trace, observation, screenshot
```

Sau restart, mọi explorer chưa Close thành **needs_recovery**. Không tự nối lại prompt, click hay chương trình đang dở. Người dùng kiểm tra Teams rồi xác nhận khôi phục; browser mới mở URL cuối với DOM mới, không có form state/cookie cũ. Run đang chạy được ghi interrupted; process trong Job Object bị dừng khi backend đóng. Run đã xong giữ log/status để model kiểm tra trước khi lập kế hoạch mới. Approval pending được giữ nhưng vẫn kiểm tra hạn/revision/runtime trước khi dùng.

Trong cùng backend, pause/grant/approval/iterate giữ đúng browser. Pause đợi ranh giới thao tác/model, không thu hồi prompt đã gửi. Ctrl+C workflow kết thúc backend nên muốn tiếp tục cần recovery. Không điều khiển cùng composer Teams bằng tay hoặc hai harness đồng thời. Các entrypoint giữ lock trên data-dir để tránh ghi đè trạng thái.

## Giới hạn thực thi

- ZIP tối đa 8 MiB nén, 32 MiB giải nén, 2.000 file; từ chối traversal, symlink, ADS, tên Windows đặc biệt, trùng Unicode/case và tỷ lệ nén bất thường.
- Approval gắn với revision, source manifest, argv, cwd, Python executable hash; hết hạn 15 phút và dùng một lần. Chạy trên bản sao riêng nên sửa source ngoài editor sau duyệt không thay mã đang chạy.
- Chỉ Python `.py` hoặc cài `requirements.txt` có từng dòng `package==version`. Không nhận URL, tùy chọn pip, nested requirements hay shell string. Package install vẫn có thể chạy mã nên cần duyệt.
- Timeout 1–600 giây; log payload tối đa 1 MiB; thu tối đa 100 output file / 8 MiB. Thư mục tạm ngắn, riêng biệt để Edge tránh MAX_PATH; xóa sau khi process kết thúc.
- Windows Job Object: helper chờ plan trước khi project chạy; parent gắn helper vào job rồi mới cấp plan. Stop/timeout/backend exit dừng descendants. Tối đa 32 process trong job.
- Venv/Job Object **không cách ly quyền filesystem/network**. Code vẫn có quyền Windows của người dùng. Chưa có container/sandbox cho code không đáng tin. Xem [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
- Browser sạch dùng Edge cài sẵn; tool actions theo allowlist, cùng origin, chặn private URL. Chưa hỗ trợ iframe/CAPTCHA/OCR/drag-drop. Không bảo đảm giải được mọi challenge.
- Prompt, response, source và log được lưu local; tool result dài có thể được upload lên Copilot. Không chia sẻ data-dir nếu chứa dữ liệu riêng tư. Bản ZIP phát hành không kèm dữ liệu phiên kiểm thử.

## Kiểm thử lặp lại

Tại thư mục nopilot, sau setup:

```bat
.venv\Scripts\python.exe -B -m unittest discover -s tests -v
set NOPILOT_INTEGRATION_TESTS=1
.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Mặc định bỏ kiểm thử cài package qua mạng. Biến môi trường trên bật thêm cài `colorama==0.4.6` từ PyPI rồi chạy import. Các test chạy code fixture đã biết, không tự duyệt mã tùy ý của Copilot. Mọi dữ liệu test dùng thư mục tạm.

Các báo cáo `*-validation-result.json` phân biệt test model/browser mô phỏng, Edge thật và Copilot thật. Live RPA dùng reviewer kiểm thử tự động chỉ chấp thuận wrapper/runtime khớp hash mã harness và requirements đã biết; bản sản phẩm luôn chờ người dùng duyệt. Bài live đã phát hiện và sửa timeout tải wheel, thiếu biến đường dẫn Edge, đường dẫn temp quá dài, và duplicate transport prompt. Không suy rộng kết quả Input Forms sang challenge khác.
