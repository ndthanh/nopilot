# Luồng phát triển dự án với Nopilot

**Luồng chính hiện tại:** dùng card Chạy thử ngay trong chat, đồng ý một lần cho kế hoạch cài/chạy. Xem [CHAT_FLOW.md](CHAT_FLOW.md). Các hướng dẫn thao tác từng bước dưới đây dành cho khu vực Nâng cao/CLI.


## Thao tác cụ thể trên Web

1. Tạo chat, nhập yêu cầu với `/develop`, ví dụ:

   ```text
   /develop Tạo máy tính Python có giao diện web local, hỗ trợ + - x :, có kiểm tra tự động và trả ZIP.
   ```

   Nopilot gửi thêm development contract v1 để Copilot trả ZIP gồm source, `nopilot.json`, README CMD, `.nopilotignore` và task kiểm tra. Nó không tự lấy lệnh trong văn xuôi/README để chạy.

2. Copilot trả ZIP, Nopilot tự tải vào artifacts. Trên thẻ ZIP, bấm **▶ Chuẩn bị dự án**, xem cây file, rồi **Giải nén vào workspace mới**. Chưa có code nào chạy. ZIP có một thư mục bọc ngoài sẽ được bỏ lớp bọc.

3. Mở **Dev → Luồng chạy dự án**. Nếu contract hợp lệ, Nopilot hiển thị tên dự án, source folder, entrypoint, args, timeout và các nút đề xuất. Nếu contract thiếu/sai, hiển thị nguyên nhân; bạn có thể sửa `nopilot.json` trong editor hoặc yêu cầu Copilot đóng gói lại. Điều khiển thủ công vẫn dùng được cho ZIP cũ.

4. Nếu có dependencies: bấm **Đề xuất cài dependencies** → xem đúng danh sách package và lệnh → xem source nếu cần → tick đồng ý → **Duyệt một lần**. Nopilot tạo venv riêng và chạy pip, ghi stdout/stderr. Chờ `succeeded` để có receipt. Sau đó source đổi nhưng pins/Python khớp thì dùng lại venv, không cần cài lại. Không cần tự activate venv. Requirements phải pin `package==version` từ PyPI.

5. Bấm **Đề xuất chạy theo manifest** hoặc **Đề xuất kiểm tra theo manifest**, rồi duyệt lệnh như trên. Mỗi task có một phiếu duyệt riêng, hết hạn sau15phút. Sửa source làm phiếu cũ không còn hiệu lực. Không có nút duyệt tất cả hay tự duyệt từ Copilot.

6. Xem **Log chạy local**: trạng thái, exit code, stdout/stderr, nút dừng cả cây process và nút mở thư mục lượt chạy. Chat ghi các mốc giải nén/đề xuất/duyệt/kết thúc và có artifact `combined.log`. Với web app đang chạy, luồng Dev hiện **Mở URL ứng dụng**. URL này do manifest khai báo, chưa phải chứng nhận health. Task `check` nên in PASS và exit0 khi thực sự kiểm tra thành công.

7. Khi cần sửa: dừng task đang chạy. Nếu cần gửi log, dùng `/upload` chọn `combined.log` từ artifacts hoặc đường dẫn tuyệt đối. **Soạn yêu cầu sửa** điền `/project "SOURCE_DIRECTORY" ...` vào chat, chưa gửi. Sửa câu hỏi, rồi gửi. `/project` áp dụng `.nopilotignore`, giữ các log bạn đã upload riêng, đóng gói source thành ZIP-TXT và hỏi Copilot. Log không tự upload.

   Nếu gửi log trước: `/upload` → chờ báo đính kèm → bấm Soạn yêu cầu sửa → sửa câu hỏi → gửi `/project`. Nếu đang có draft, nút soạn không ghi đè draft.

8. ZIP sửa nhận về có hai lựa chọn: chọn project hiện có → **Xem diff → Áp dụng ZIP + commit local** để giữ venv khi pins/Python khớp; hoặc giải nén thành workspace mới với venv riêng. Checkpoint/Git giữ source trước cập nhật. Xem [GIT_ITERATION.md](GIT_ITERATION.md). Với sửa nhỏ tại editor Nopilot, có checkpoint/diff/rollback và vẫn dùng venv của chính project đó.

## Convention của ZIP Python v1

```text
my-app/
  nopilot.json
  .nopilotignore
  NOPILOT_COMMIT_MESSAGE.txt  # commit message Copilot viết
  README.md
  requirements.txt   # chỉ khi có dependencies
  app.py
  check.py
  ...source/assets...
```

Ví dụ `nopilot.json`:

```json
{
  "schemaVersion": 1,
  "name": "Local calculator",
  "runtime": "python",
  "install": {"requirements": "requirements.txt", "timeoutSeconds": 300},
  "tasks": {
    "start": {"entrypoint": "app.py", "args": [], "timeoutSeconds": 600},
    "check": {"entrypoint": "check.py", "args": [], "timeoutSeconds": 120}
  },
  "previewUrl": "http://127.0.0.1:8899/"
}
```

Với thư viện chuẩn: `"install": null`, bỏ requirements. Với CLI batch: args chứa input, ví dụ `["--expr", "2 + 3 x 4"]`; không khai báo previewUrl. Task check tùy chọn nhưng nên có, tự chạy độc lập và không cần start đang chạy. Unknown keys, path ra ngoài project, shell command và entrypoint không phải `.py` bị từ chối. Schema trao đổi nằm trong [nopilot.schema.json](nopilot.schema.json); validator còn kiểm tra file tồn tại, đường dẫn Windows, pinned requirements và URL loopback.

## Thư mục và trạng thái

```text
DATA/conversations/CONVERSATION_ID/
  artifacts/downloads/                 # ZIP Copilot trả về
  dev/projects/PROJECT_ID/source/      # source để đọc/sửa/đóng gói lại
  dev/projects/PROJECT_ID/venv/        # dependency riêng, ngoài source
  dev/projects/PROJECT_ID/approved-sources/APPROVAL_ID/  # cwd của lượt chạy
  artifacts/runs/RUN_ID/               # run.json, stdout/stderr, combined.log, outputs
```

Chạy trên snapshot đúng revision được duyệt. File chương trình sinh ra nằm trong snapshot; Nopilot thu output có giới hạn vào artifacts, không tự chép chúng về source. Nếu muốn sửa dữ liệu/source từ output, bạn chủ động copy về source trước khi `/project`. Mở folder source và folder lượt chạy là hai nút khác nhau.

Luồng trạng thái: `ZIP → imported → contract valid → install pending → install succeeded → start/check pending → running → succeeded/failed/stopped/timeout → repair`. Phiếu duyệt và lượt chạy được lưu, khởi động lại backend không tự chạy lại mã hoặc gửi lại prompt. Các bước chạy trên Windows có quyền tài khoản hiện tại; venv không phải sandbox.

## Phạm vi hiện tại

- Python scripts hoặc web app loopback; không chạy tùy ý `.cmd`, npm, Docker Compose hay migration command từ manifest.
- Không có terminal tương tác: stdin đóng, `input()` sẽ không hoạt động. Dùng args hoặc giao diện web. Máy tính CLI có vòng `input()` nhận từ ZIP cũ cần thêm chế độ args hoặc chuyển sang web.
- Mỗi task tối đa600giây, log1MiB; chưa phải daemon/dev server chạy cả ngày. Dừng trước khi sửa source; chưa chạy check song song với start cùng project.
- Web app nên tắt reloader/debug, bind127.0.0.1. Task check phải tự setup/cleanup nếu kiểm tra HTTP, vì nó chạy độc lập.
- Apply ZIP vào project cũ cần xem diff và đồng ý; Git local và venv reuse được mô tả trong GIT_ITERATION.md. Chưa có auto merge, streaming UI của app hay tự gửi log. Các giới hạn import ZIP và upload ZIP-TXT vẫn giữ nguyên.

## CLI bằng CMD

Trong CLI chat dùng `/develop yêu cầu`. Nhận ZIP bằng `/download`, sau đó:

```bat
nopilot.cmd dev extract "C:\work\app.zip"
nopilot.cmd dev plan PROJECT_ID
nopilot.cmd dev task PROJECT_ID install
nopilot.cmd dev task PROJECT_ID check
nopilot.cmd dev task PROJECT_ID start
```

Bỏ install nếu contract `install:null`. Mỗi `task` hiển thị lệnh và yêu cầu gõ `RUN APPROVAL_PREFIX` để duyệt một lần. Nếu đổi `--data-dir`, dùng cùng đường dẫn cho tất cả lệnh. Ví dụ `nopilot.cmd dev --data-dir "C:\work\dev" plan PROJECT_ID`.

## Bằng chứng kiểm thử 24/10/2026

Đã dùng UI Nopilot gửi `/develop` cho Copilot thật, nhận `NopilotContractCalculator.zip`, xem cây ZIP, giải nén, nhận diện contract và tạo phiếu duyệt `check` đúng entrypoint/args/revision/timeout. UI được kiểm thử đến bước chờ người dùng duyệt, không bấm tự duyệt mã Copilot. Nút Soạn yêu cầu sửa điền đúng source path và chưa gửi; đã sửa lỗi polling vẽ lại nút gây mất thao tác bấm.

Sau khi đọc source, kiểm thử riêng chính ZIP đó bằng runner/contract trong workspace kiểm thử khác: tạo venv tự động, `check` in `CHECK_PASS`, `start` in `RESULT=14`, cả hai exit0. Luồng install/start dùng fixture mã nguồn biết trước và `colorama==0.4.6` từ PyPI cũng thành công. Kết quả và log lưu trong `nopilot-development-validation.zip` bên cạnh gói phát hành.

Bộ test92:91pass,1skip integration cài package; việc cài package thật theo contract đã được kiểm tra riêng như trên. Bản này chưa kiểm thử end-to-end URL preview của web server mới; preview link chỉ biểu diễn URL khai báo, chưa kiểm tra health. Task đang chờ duyệt trong UI có thể dùng để bạn tiếp tục thử.
