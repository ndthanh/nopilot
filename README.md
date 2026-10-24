# Nopilot — Web và CLI cho Teams Copilot trên Windows

**Bắt đầu từ code có sẵn:** chọn **Workspace** hoặc `/workspace "C:\src\my-project"`, duyệt nhập bản sao source theo `.nopilotignore` và lưu Git backup. Sau đó dùng `/iterate yêu cầu sửa` để gửi source hiện tại, nhận ZIP và duyệt cập nhật/cài/chạy. Tài liệu từng bước mở bằng nút **Hướng dẫn** trong Web UI hoặc [bản HTML](web/help.html). Workspace là bản sao Nopilot quản lý; thư mục và Git repo gốc được giữ nguyên.

**Luồng chat đơn giản:** ZIP Copilot trả về có card **Chạy thử** ngay trong chat. Một lần đồng ý để Nopilot chuẩn bị Git, cài dependencies nếu cần rồi chạy theo contract. ZIP sửa cập nhật project cũ sau khi xem kế hoạch/diff; venv được giữ khi còn khớp. Xem [CHAT_FLOW.md](CHAT_FLOW.md). **Nâng cao** là tùy chọn.

**Iterate nhanh + Git:** ZIP sửa có thể apply vào project hiện có sau khi xem diff, giữ venv khi pins/Python khớp và commit local bằng message Copilot viết. Xem [GIT_ITERATION.md](GIT_ITERATION.md).

**Tạo và chạy dự án:** dùng nút **Tạo dự án** hoặc `/develop yêu cầu`. Copilot trả ZIP có `nopilot.json`; chọn **Chạy thử** trên card trong chat. Cài/chạy được điều phối theo một kế hoạch đã đồng ý; điều khiển từng bước vẫn có trong Nâng cao. Đọc [DEVELOPMENT.md](DEVELOPMENT.md) để xem toàn bộ luồng, schema và cách iterate. Log vẫn gửi riêng bằng `/upload`.

**Bản nâng cấp độ tin cậy 24/10/2026:** checkpoint + memory, kiểm tra schema cả batch, ảnh có nhãn image_id, phát hiện vòng lặp, browser diagnostics, kiểm chứng replay trong browser mới và container tùy chọn. Đọc [RELIABILITY.md](RELIABILITY.md) để xem cách dùng, kết quả và giới hạn; [UI_TESTING.md](UI_TESTING.md) ghi quy trình kiểm thử qua UI/Copilot thật và kết quả16/20lượt. Container chưa được kiểm chứng end-to-end trên máy này vì Docker engine chưa chạy.

**Đổi tên:** công cụ nay là **Nopilot**. Chạy `setup.cmd` lại để cài thêm dependency `pathspec`, sau đó dùng `nopilot.cmd` / `nopilot-web.cmd`; alias lệnh cũ vẫn hoạt động. Để giữ lịch sử, dùng lại cùng `--data-dir` (phiên đang mở tiếp tục dùng thư mục dữ liệu cũ). Nếu chỉ dùng đường dẫn mặc định, Nopilot tự dùng lại thư mục mặc định cũ khi thư mục mới chưa tồn tại.

**Project ignore:** đặt `.nopilotignore` tại gốc dự án. Copy file mẫu đi kèm rồi chỉnh theo cú pháp `.gitignore`. Xem [PROJECT_LOOP.md](PROJECT_LOOP.md).

**Bắt đầu nhanh:** chạy `setup.cmd`, sau đó `nopilot-web.cmd` và mở `http://127.0.0.1:8765`. Muốn dùng terminal: `nopilot.cmd`. Đọc web: `/url URL câu hỏi`. Tất cả lệnh chạy bằng CMD/Python.



nopilot gửi prompt, nhận phản hồi, upload log và tải artifact thông qua Frida gắn vào Teams đang chạy. Không cần PowerShell, CDP, remote debugging, clipboard hay thao tác chuột/bàn phím hệ thống.

Phần tìm process dùng Windows Toolhelp API trực tiếp qua `ctypes`; các script không gọi shell để tìm PID. Discovery dùng `VirtualQueryEx`/`ReadProcessMemory` từ process Python, bỏ qua trang guard/noaccess; không còn chạy `Memory.scanSync` trên toàn bộ bộ nhớ bên trong Teams. Chat CLI không tự thực thi code do Copilot sinh ra. Luồng `workflow` mới chỉ chạy sau khi người dùng duyệt từng lần. `loop_demo.py` là demo riêng, chỉ chạy code nằm trong allowlist cố định.

## 1. Cài bằng CMD

Yêu cầu: Windows x64, Python x64 3.10 trở lên, Microsoft Teams desktop và Copilot Chat đã mở. Lần cài đầu cần tải package Frida từ pip. Không cần activate môi trường ảo.

Giải nén bộ mã, mở **Command Prompt (cmd.exe)** tại thư mục `nopilot`, chạy:

```bat
setup.cmd
nopilot.cmd open
nopilot.cmd status
nopilot.cmd
```

`setup.cmd` tạo `.venv` và cài các package trong `requirements.txt`. `nopilot.cmd open` mở lại màn hình Copilot qua nút điều hướng trong WebView Teams nếu cần. `nopilot.cmd status` chỉ tìm và đọc trạng thái ô chat, không chuyển trang. `nopilot.cmd` mở phiên CLI tương tác và tự mở Copilot nếu chưa ở màn hình chat.

Nếu muốn gọi Python trực tiếp, các lệnh tương đương là:

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -B cli.py open
.venv\Scripts\python.exe -B cli.py status
.venv\Scripts\python.exe -B cli.py chat
```

Nếu đã có một môi trường Python chứa Frida, có thể chọn nó mà không cần cài lại:

```bat
set "COPILOT_PYTHON=C:\path\to\python.exe"
nopilot.cmd status
```

Nếu có nhiều Teams host, truyền PID rõ ràng: `nopilot.cmd --pid 12345 status`. Nếu không truyền, CLI tự loại các process con `ms-teams.exe` và chọn một host gốc.

## 2. Chat tương tác trong terminal

```bat
nopilot.cmd
```

Khi thấy `nopilot>`, nhập prompt rồi Enter. Phản hồi được in khi bridge xác nhận hoàn tất; hiện chưa stream token trực tiếp.

| Lệnh trong phiên chat | Tác dụng |
|---|---|
| `/help` | Xem lệnh |
| `/status` | PID, UI thread, frame, trạng thái ô nhập |
| `/read` | Đọc phản hồi gần nhất, không gửi thêm prompt |
| `/new` | Mở phiên Copilot mới; giữ nguyên chat cũ trong lịch sử |
| `/multiline` | Nhập nhiều dòng; kết thúc bằng một dòng `/send` |
| `/cancel` | Chỉ dùng trong `/multiline`, bỏ phần đang nhập ở terminal |
| `/file "prompt.txt"` | Gửi prompt UTF-8 từ file |
| `/upload "local-log.txt"` | Upload file và chờ composer báo upload finished |
| `/url https://example.com câu hỏi` | Đọc URL thành Markdown, gửi inline hoặc upload MD |
| `/project current yêu cầu sửa` | Web: tự lấy source project đang dùng trong conversation, nén ZIP đuôi TXT và gửi; không chọn thư mục lại |
| `/project "C:\src\my-app" yêu cầu sửa` | Đóng gói source thành ZIP mang đuôi TXT, giữ log đã upload riêng và gửi yêu cầu sửa; xem [PROJECT_LOOP.md](PROJECT_LOOP.md) |
| `/downloads` | Liệt kê tên file tải được trong lượt trả lời cuối |
| `/download "project.zip" "C:\work\project.zip"` | Đọc file từ link và lưu local |
| `/reconnect` | Tìm lại PID/thread/frame sau khi Teams restart hoặc frame thay đổi |
| `/open` | Chuyển Teams về màn hình Copilot, rồi kết nối lại |
| `/quit` | Ngắt kết nối, thoát CLI |

Ví dụ prompt nhiều dòng:

```text
nopilot> /multiline
... Hãy xem log sau:
... stdout: 323
... exit code: 0
... Giải thích kết quả bằng tiếng Việt.
... /send
```

Cách thao tác từng bước:

1. Ở dấu nhắc `nopilot>`, gõ `/multiline` rồi Enter.
2. CLI hiện dấu nhắc `... `. Nhập dòng thứ nhất rồi Enter; nhập tiếp những dòng sau. Enter lúc này chỉ thêm dòng, **chưa gửi**.
3. Để gửi tất cả các dòng thành **một prompt duy nhất**, gõ `/send` trên một dòng riêng rồi Enter.
4. Muốn bỏ phần vừa nhập ở terminal, gõ `/cancel` trên một dòng riêng. Chưa có nội dung nào được gửi tới Copilot.

Không tự gõ chữ `nopilot>` hoặc `...`; đó là dấu nhắc CLI tự in. Bạn có thể dán nhiều dòng rồi nhập `/send`. Nếu nội dung cần có nguyên dòng `/send` hoặc `/cancel`, dùng `/file "prompt.txt"` để không bị hiểu thành lệnh điều khiển.

Để chuyển sang chat mới, gõ `/new` tại dấu nhắc `nopilot>`. Lệnh này bấm nút New chat trong DOM rồi chờ lịch sử hiển thị trống và ô nhập sẵn sàng. Nó không xóa chat cũ và không gửi prompt. Nếu có draft, attachment chưa gửi, hoặc Copilot đang sinh câu trả lời, lệnh dừng thay vì tự bỏ nội dung đó. `/new` gõ trong chế độ `/multiline` sẽ được coi là một dòng nội dung; hãy kết thúc hoặc hủy multiline trước.

`/reconnect` không tự gửi lại prompt đang chờ. Sau một lần bị ngắt hoặc quá hạn, dùng `/read` để kiểm tra trước khi quyết định gửi lại. Nếu Teams chưa mở lại Copilot Chat, mở trang đó rồi chạy `/reconnect`.

## 3. Lệnh riêng lẻ cho script hoặc vòng lặp local

Các option chung như `--json`, `--pid`, `--journal` đặt **trước** tên subcommand.

```bat
nopilot.cmd --json status
nopilot.cmd ask -p "Reply with exactly OK"
nopilot.cmd --json ask -f prompt.txt --timeout 300 -o response.json
nopilot.cmd --json read
nopilot.cmd --json new
```

`prompt.txt` phải là UTF-8, có hoặc không có BOM. `-o` ghi toàn bộ kết quả JSON vào một file mới, không ghi đè. Prompt chứa code, nhiều dòng, dấu ngoặc kép hoặc ký tự đặc biệt của CMD nên để trong file.

Đọc prompt từ stdin:

```bat
type prompt.txt | nopilot.cmd --json ask -f -
```

Mã thoát: `0` thành công, `1` lỗi, `130` bị ngắt bởi Ctrl+C. Khi có `--json`, stdout chứa JSON; lỗi được ghi vào stderr. `--json` chỉ dành cho các lệnh riêng lẻ, không áp dụng cho `chat`.

Ghi nhật ký yêu cầu/phản hồi khi cần:

```bat
nopilot.cmd --journal work\session.jsonl chat
nopilot.cmd --json --journal work\session.jsonl ask -f prompt.txt
```

Journal là tùy chọn, không mặc định thu thập nội dung chat. Khi bật, nó lưu prompt và phản hồi của những yêu cầu được gửi qua chính phiên CLI đó. Journal không tự chống gửi trùng qua các lần chạy, nhưng giữ request ID và trạng thái để bạn kiểm tra khi một lượt bị ngắt.

Ví dụ tích hợp bằng Python, hoàn toàn không gọi shell:

```python
import json
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "cli.py", "--json", "ask", "-f", "prompt.txt"],
    capture_output=True, text=True, encoding="utf-8", timeout=360,
)
if result.returncode:
    raise RuntimeError(result.stderr)
reply = json.loads(result.stdout)
print(reply["answer"])
```

Hoặc giữ một kết nối lâu dài trong chương trình Python:

```python
from cli import Harness

harness = Harness(journal="work/session.jsonl")
try:
    print(harness.connect())
    answer = harness.ask("Một prompt riêng cho lượt này", timeout=300)
    print(answer["answer"])
finally:
    harness.close()
```

## 4. Upload log và tải file

```bat
nopilot.cmd --json upload local-log.txt
nopilot.cmd ask -p "Read the attached log and explain the error."
nopilot.cmd --json downloads
nopilot.cmd --json download project.zip downloaded-project.zip
```

Upload: Python đọc file bạn chọn, chuyển byte qua Frida, tạo `File`/`DataTransfer` trong frame và đưa vào input upload. CLI chờ composer hiện tên file và trạng thái `upload finished`; với giao diện mới không có dòng trạng thái đó, nó nhận diện attachment card đã có ID dạng `SPO_`, nút remove và không còn progress, ổn định qua ba lần đọc. Kết quả trả về ghi rõ tín hiệu nào đã dùng. Đây là heuristic giao diện; phép thử đọc nội dung từ Copilot mới xác nhận file thực sự đọc được. Các nhãn lỗi/trạng thái văn bản hiện được nhận diện bằng tiếng Anh. Teams đã thông báo rằng file upload được lưu vào OneDrive của tài khoản.

Download: CLI tìm link có thuộc tính `download` trong lượt trả lời cuối. Nếu là `blob:`, bridge gọi `fetch(blobUrl)` **bên trong chính frame Copilot**, chuyển dữ liệu thành byte/base64 qua Frida RPC, rồi Python giải mã và ghi file local. Không kích hoạt link bằng click, không gọi Download Manager của Teams/Edge và không dùng tính năng sync OneDrive, nên không có animation download của ứng dụng.

```text
Link blob trong frame Copilot
        ↓ fetch trong cùng frame
Byte của file → base64 → Frida RPC → Python → file local
```

URL `blob:` là tham chiếu do trình duyệt quản lý, không phải đường dẫn HTTP tới OneDrive. Cơ chế này không chứng minh file nguồn có hay không nằm trên OneDrive: ứng dụng có thể đã tạo hoặc lấy dữ liệu rồi cung cấp dưới dạng Blob. Các thử nghiệm trước đã đọc được TXT và ZIP bằng link Blob mà không truy cập trực tiếp API OneDrive, không trích cookie hay token tài khoản.

Giới hạn PoC: mỗi file upload/download tối đa 1 MiB; chỉ tải link `blob:`, `data:` hoặc `https:` có thuộc tính `download`. HTTPS vẫn chịu quy tắc CORS của trang. Thư mục đích phải có sẵn; file đích không được tồn tại. Link Blob có thể hết hiệu lực khi trang/frame bị đóng hoặc thay thế: sau restart cần yêu cầu Copilot cung cấp lại file nếu link cũ không còn đọc được.

### Gửi dự án nhiều file bằng một attachment

Trong phiên chat:

```text
/project "C:\src\my-app"
```

Hoặc từ CMD, kèm yêu cầu cụ thể:

```bat
nopilot.cmd project "C:\src\my-app" -q "Đọc dự án và tìm nguyên nhân gây lỗi import."
nopilot.cmd --json project "C:\src\my-app" --question-file question.txt --out-dir "C:\work\project-bundles"
```

Quy trình: đọc các file được chọn → tạo ZIP nhị phân nguyên vẹn → ghi ZIP dưới tên `project-<id>.txt` → upload một attachment → gửi prompt tự động giải thích ZIP mang đuôi TXT và yêu cầu Copilot mở archive để đọc. Đây là byte ZIP thật, không phải base64 hay nội dung text ghép. Không cần upload từng file nguồn, nên một dự án chỉ chiếm **1 trong tối đa 3 attachment**.

Bên trong archive có `_HARNESS_PROJECT_MANIFEST.json` ghi đường dẫn tương đối, kích thước và SHA-256 từng file. Packer cũng tạo manifest và prompt thành hai file riêng ở local để kiểm tra; hai file này **không được upload**. Mặc định artefact local nằm trong `work/project-bundles/`. Có thể upload tối đa2log riêng trước `/project`; project dùng thêm một attachment. Web chat ghi từng bước đóng gói, bỏ qua file, upload và chờ trả lời. Xem [PROJECT_LOOP.md](PROJECT_LOOP.md) để dùng câu hỏi sửa và `--exclude`.

Chỉ đóng gói, chưa kết nối hoặc upload vào Teams:

```bat
nopilot.cmd --json pack "C:\src\my-app" -o "C:\work\my-app-project.txt"
python -m zipfile -l "C:\work\my-app-project.txt"
```

Các file được tạo là `my-app-project.txt`, `my-app-project.manifest.json` và `my-app-project.prompt.txt`. Nếu muốn gửi thủ công:

```bat
nopilot.cmd upload "C:\work\my-app-project.txt"
nopilot.cmd ask -f "C:\work\my-app-project.prompt.txt"
```

Packer mặc định bỏ `.git`, `node_modules`, các thư mục venv/cache/build, `.env`/`.env.*`, các mẫu file private key và một số binary/database. Đây là mẫu loại trừ, không phải bộ phát hiện mọi bí mật. Dùng `--exclude GLOB` nhiều lần để bỏ thêm dữ liệu không cần gửi:

```bat
nopilot.cmd project "C:\src\my-app" --exclude "*.log" --exclude "assets/*" -q "Giải thích cấu trúc mã nguồn."
```

`--exclude` dùng glob đơn giản trên đường dẫn tương đối hoặc tên file; chưa áp dụng `.gitignore`. Symlink/junction bị bỏ qua. Bundle và các file companion không được ghi đè. Thư mục output phải nằm ngoài thư mục dự án để tránh tự đóng gói artifact của chính nó. Nếu chạy harness từ chính root dự án, chọn `--out-dir` ở ngoài root.

Giới hạn hiện tại: tối đa 2.000 file, 16 MiB dữ liệu nguồn trước nén và 1 MiB ZIP sau nén. Nếu vượt, lệnh dừng trước upload. Bridge chặn attachment thứ tư ở composer; dự án được đóng gói không cần chia thành ba phần.

Prompt yêu cầu Copilot nói rõ `ACCESS_UNAVAILABLE` nếu không truy cập được byte gốc, không tự suy đoán là đã đọc archive. Trên phiên kiểm thử hiện tại, dự án mẫu gồm 3 file được gửi qua ZIP 1.043 byte mang đuôi TXT; Copilot đọc đúng proof ngẫu nhiên chỉ có trong file JSON và liệt kê đúng đường dẫn nguồn. Xem `project-bundle-validation-result.json`. Khả năng này còn phụ thuộc cách xử lý attachment của từng phiên/tài khoản; kết quả thử ở đây không khẳng định mọi môi trường đều xử lý giống nhau.

## 5. Khi Teams hoặc WebView2 thay đổi

Sau Teams restart, một lệnh CLI mới tự tìm PID/thread/frame mới. `open`, `chat`, `ask`, `new`, `read`, `upload`, `project`, `downloads`, `download` tự tìm và kích hoạt nút Copilot trong Teams shell nếu chưa tìm được ô nhập; `status` giữ chế độ chỉ đọc. `pack` hoạt động offline, không attach vào Teams. Phiên CLI đang mở cần `/reconnect`.

Cơ chế mở lại có hai tầng: tìm WebView gốc của Teams → tìm duy nhất nút điều hướng có nhãn `Copilot` → DOM click → chờ frame và ô nhập sẵn sàng tối đa 30 giây. Không gửi Ctrl+6 bằng bàn phím hệ thống. Nếu nút thiếu hoặc có nhiều nút mơ hồ, bridge dừng để bạn kiểm tra. Nó không tự khởi chạy Teams khi ứng dụng đã tắt, không tự đăng nhập, và không tự gửi lại những lượt đang dở.

Bridge kiểm tra SHA-256 của `EmbeddedBrowserWebView.dll` trước khi dùng offset native. Nếu WebView2 cập nhật và báo build mismatch:

```bat
.venv\Scripts\python.exe -B refresh_build.py
nopilot.cmd status
```

Script lấy public PDB đúng phiên bản từ symbol server của Microsoft bằng Python, cache vào `work/teams-frida-symbols/`, rồi tạo lại `build.json`. Không gọi PowerShell. Nếu symbol thiếu hoặc mơ hồ, script dừng. Việc tạo manifest mới chưa bảo đảm mọi thay đổi giao diện hoặc API ở phiên bản tương lai tương thích.

## 6. Phạm vi kiểm thử và giới hạn

Môi trường: Teams `26225.1806.5074.1452`, WebView2 `155.0.4283.62`, Windows/Python x64. Kết quả cũ trong gói là các thử nghiệm trên phiên trước; `cli-validation-result.json` ghi các phép thử mới sau restart.

- Phiên trước: chat, prompt nhiều dòng, vòng code → local execution → log → xác nhận, upload TXT, download TXT, download ZIP có hai file và chạy chương trình nhỏ thành công.
- Trong kiểm thử bản discovery cũ sau restart, Windows ghi nhận hai lần Teams crash ở `ntdll.dll`, exception `0xc00000ff`. Chưa chứng minh được nguyên nhân gốc. Bản này đã bỏ quét bộ nhớ trong target, chuyển sang đọc bộ nhớ từ Python và loại trừ trang guard/noaccess. Các kết quả CLI của bản sửa được ghi trong `cli-validation-result.json`; đây chưa phải cam kết ổn định dài hạn.
- Bản sửa đã qua gửi/nhận prompt tiếng Việt nhiều dòng, đọc phản hồi, phiên terminal tương tác, reconnect, CMD launcher, download Blob và đọc đúng proof trong file upload. Kiểm thử bổ sung chuyển từ Chat thường về Copilot bằng `open`, sau đó 8 kết nối liên tiếp tìm được ô nhập với cùng PID. Xem `cli-validation-result.json` và `recovery-validation-result.json`. Kiểm thử `/multiline`, `/cancel`, `/send`, `/new` được ghi trong `new-multiline-validation-result.json`.
- Đây là reverse engineering trong native host. DOM, test-id, API nội bộ Lexical hoặc symbol có thể thay đổi. Callback native đang pending thì bridge từ chối chủ động unload code của nó.
- Hoàn tất phản hồi được nhận diện bằng nút Copy, trạng thái Stop và nội dung ổn định qua nhiều lần đọc; đây là heuristic giao diện, chưa phải tín hiệu giao thức chính thức. Transcript dài có thể bị virtualize; `/read` và phát hiện trùng chỉ dựa trên lượt hiện có trong DOM.
- Code block dài có thể chỉ có một phần dòng trong DOM. Dùng artifact ZIP tải xuống khi cần mã đầy đủ của dự án nhiều file.
- Đã có executor Python với duyệt từng lần, checkpoint/diff và dừng cây process; xem mục 10. Venv và Job Object không phải sandbox bảo mật. `loop_demo.py` cũ vẫn chỉ chạy AST cố định.
- CLI đang dành cho một người điều khiển một chat. Tránh vừa sửa composer bằng tay vừa gửi từ CLI, hoặc chạy đồng thời nhiều CLI gửi vào cùng chat.

Xem toàn bộ lệnh bằng `nopilot.cmd --help`, `nopilot.cmd ask --help`. Các API mức thấp trong `bridge.py` vẫn dùng được cho phát triển, nhưng hướng dẫn thông thường ưu tiên `cli.py` và `nopilot.cmd`.

## 7. Đọc URL thành context — đã triển khai

Không cần API tìm kiếm hay trình duyệt. Bạn cung cấp URL công khai muốn đọc; Python tải HTML bằng `urllib`, BeautifulSoup tách nội dung chính, `markdownify` chuyển sang Markdown và giữ đường dẫn nguồn. Các script, menu điều hướng và phần phụ được bỏ trước khi chuyển đổi. Đây là bộ đọc URL cụ thể, chưa có tìm kiếm web tự động.

Trong CLI hoặc Web:

```text
/url https://docs.python.org/3/library/pathlib.html Giải thích cách duyệt thư mục bằng pathlib
```

Từ CMD:

```bat
nopilot.cmd url https://example.com -q "Tóm tắt trang này"
nopilot.cmd --json url https://docs.python.org/3/library/pathlib.html -q "Giải thích Path.glob" --context-mode auto
nopilot.cmd url https://example.com --local-only --out-dir "C:\work\web-context"
```

Chế độ `auto` gửi context không quá **10.000 ký tự** trực tiếp trong prompt. Nếu dài hơn, harness lưu thành `.md`, upload một attachment rồi yêu cầu Copilot đọc file trước khi trả lời. `--context-mode file` ép upload; `inline` ép gửi text nhưng từ chối trên 24.000 ký tự. Bản Markdown và metadata JSON (URL, thời gian lấy, số byte, SHA-256) luôn được lưu local, kể cả khi gửi inline. `--local-only` chỉ tải và lưu, không kết nối Teams.

Trong Web, context nằm trong artifacts của conversation. CLI mặc định lưu ở `work/nopilot-cli/conversations/<conversation-id>/artifacts/context/`; có thể đổi bằng `--out-dir`. Context upload vẫn tính vào giới hạn 3 attachment. File được đưa lên dịch vụ Microsoft theo cùng cơ chế upload đã mô tả ở trên.

Giới hạn: chỉ HTML/text trả về từ máy chủ, **không chạy JavaScript**, không dùng cookie của trình duyệt, không đọc trang cần đăng nhập và không vượt CAPTCHA. Trang chỉ có nội dung sau khi chạy JavaScript có thể thiếu dữ liệu; kết quả chuyển đổi cần được kiểm tra với nguồn. Mỗi lần đọc một URL, tối đa 2 MiB HTML và 1 MiB Markdown; không tự crawl các link con. URL riêng tư/localhost/link-local bị từ chối. Trang nguồn được đánh dấu là dữ liệu không đáng tin trong prompt.

Kiểm thử trực tiếp đã xác nhận: Example Domain gửi inline; tài liệu pathlib khoảng 99.000 ký tự tự upload Markdown, Copilot đọc đúng mã proof chỉ có trong file. Kết quả trong `url-context-validation-result.json`.

## 8. Giao diện Web local

```bat
nopilot-web.cmd
```

Mở `http://127.0.0.1:8765` trong trình duyệt. Để chọn port và nơi lưu dữ liệu:

```bat
nopilot-web.cmd --port 8765 --data-dir "C:\work\nopilot-data"
```

Hoặc gọi Python trực tiếp:

```bat
.venv\Scripts\python.exe -B web_server.py --port 8765 --data-dir "C:\work\nopilot-data"
```

Web có chat, danh sách conversation, nút tạo chat mới, kết nối lại Teams và bảng artifacts. Nút mặt trăng/mặt trời ở thanh trên chuyển giao diện sáng/tối. Lựa chọn được lưu trong trình duyệt và áp dụng trước khi trang vẽ để tránh lóe nền trắng. Khi chưa chọn, nopilot theo theme hệ điều hành. Sau cập nhật hãy restart backend và tải lại trang để nhận file `theme.js` mới. **Enter** gửi, **Shift+Enter** xuống dòng. **Tab** hoàn thành slash command: `/up` → `/upload`. Sau khi hoàn thành `/upload` hoặc `/project`, nopilot mở hộp chọn file/thư mục Windows bằng backend; chọn xong chỉ điền đường dẫn, chưa gửi và chưa upload. Có thể hủy hộp chọn rồi tự gõ đường dẫn. Cần Python có tkinter (bản Windows tiêu chuẩn thường có sẵn). Chọn **Đọc URL** rồi nhập URL cùng câu hỏi, hoặc dùng `/url` ngay trong chế độ Chat.

Không có ô chọn file HTML. Nhập đường dẫn tuyệt đối vào chat:

```text
/upload "C:\work\logs\build-log.txt"
```

Backend sao chép file vào artifacts của conversation rồi upload byte qua bridge. Sau thông báo đã đính kèm, gửi câu hỏi về file ở lượt kế tiếp. Đường dẫn là đường dẫn trên máy chạy backend. `/project "C:\src\my-app"` gửi dự án qua một attachment; `/new` tạo cả conversation local và chat Copilot mới. `/multiline` chỉ dùng trong CLI; Web dùng Shift+Enter.

File Copilot trả về được tự tải (tối đa 5 file/lượt, 1 MiB/file) và hiện thành thẻ trong chat/bảng artifacts. Bấm mũi tên tải file; nút thư mục trên từng thẻ mở Explorer tại thư mục chứa file đó. **Mở thư mục conversation** mở thư mục artifacts chung. `/downloads` liệt kê link hiện có, `/download "ten-file.txt"` tải thủ công khi cần. Link Blob cũ có thể hết hạn sau khi Teams thay frame.

```text
<data-dir>/
  conversations/
    <local-conversation-id>/
      conversation.json
      journal.jsonl
      artifacts/
        context/          # Markdown và metadata của URL
        uploads/          # Bản sao file người dùng chọn bằng đường dẫn
        downloads/        # File do Copilot trả về
        project-bundles/  # ZIP mang đuôi TXT và companion local
```

Web lưu lịch sử nội dung, artifacts và journal trên máy; giữ nguyên `--data-dir` khi khởi động lại. Chọn conversation cũ để xem lịch sử; khi gửi tiếp, backend cố mở lại đúng conversation Copilot bằng ID đã lưu. Nếu có draft/attachment chưa gửi hoặc đang sinh trả lời ở chat khác, thao tác chuyển bị từ chối để tránh mất nội dung. Lịch sử local chỉ gồm các lượt qua nopilot, không tự nhập toàn bộ lịch sử Teams. Mỗi conversation có nút **Ghim/Bỏ ghim** và **Xóa chỉ trong nopilot**. Ghim đưa conversation lên đầu danh sách. Xóa chỉ ẩn conversation local; metadata/artifacts được giữ với `deletedAt` để có thể khôi phục thủ công. Hai thao tác này không gọi bridge và không ghim/xóa bên Copilot. Conversation đang chạy job phải hoàn tất trước khi xóa. Không xóa chat Copilot từ giao diện này.

Một worker tuần tự hóa thao tác Teams. Chỉ chạy một Web backend hoặc một CLI gửi tin tại một thời điểm; không thao tác composer Teams song song. Backend chỉ bind `127.0.0.1`, kiểm tra Host/Origin và token local cho POST, không cần cloud hosting hay Node.js. Chỉ dùng trên máy cá nhân đáng tin cậy vì backend có quyền đọc đường dẫn local do bạn nhập. Ctrl+C tại cửa sổ CMD dừng server.

Kiểm thử Web được ghi trong `web-ui-validation-result.json`; đây là giao diện local thử nghiệm, chưa phải dịch vụ nhiều người dùng. Bản phát hành không chứa lịch sử, dữ liệu tài khoản hay file cá nhân từ phiên kiểm thử.

## 9. Playwright as a tool — thử nghiệm, mặc định 20 lượt

Đọc URL bằng `/url` vẫn không cần Playwright. Để bật browser tool, cài dependency tùy chọn:

```bat
.venv\Scripts\python.exe -m pip install -r requirements-browser.txt
```

Không cần tải Chromium riêng vì runner dùng Microsoft Edge đã cài. Browser tool mở một context sạch chạy nền, không dùng profile đăng nhập Teams và không chiếm chuột/bàn phím. Trên Web chọn **Playwright tool**, nhập URL cùng yêu cầu; hoặc:

```text
/browse https://rpachallenge.com/ Khám phá và tự động hóa các challenge. Với mỗi challenge thành công, xuất project ZIP Python Playwright riêng và README chạy lại.
```

Từ CMD:

```bat
nopilot.cmd workflow --data-dir "C:\work\nopilot-workflow" start https://rpachallenge.com/ -q "Giải Input Forms, xuất project Python Playwright, sửa README rồi đề xuất cài và chạy lại, chờ tôi duyệt từng lần"
```

Harness gửi một prompt điều phối chứa giao thức và quan sát trang ban đầu. Đây là **instruction message trong chat**, không phải quyền system-role thật của dịch vụ Copilot. Copilot trả một JSON tool call/lượt; Python xác thực run ID, call ID, tên tool và arguments rồi thực hiện. Kết quả/lỗi được feed lại để Copilot quyết định bước kế tiếp. JSON sai có tối đa hai lượt sửa; các lượt sửa cũng tính trong **20 lượt model**. Mỗi tool call có thể chứa nhiều thao tác browser, nên 20 lượt không có nghĩa 20 click.

```json
{"type":"tool_call","run_id":"...","id":"call_1","tool":"playwright","arguments":{"actions":[{"action":"snapshot"}]}}
```

Tool có `goto`, `snapshot`, `inspect`, `click`, `fill`, `select`, `check`, `press`, `wait`, `assert_text`, download file công khai, đọc sheet đầu của XLSX và lặp các dòng để điền form. Quan sát gồm text, links, attributes của inputs và buttons, giá trị input hiện tại, checked state và giá trị options. `inspect(selector)` đọc text/attributes/outerHTML/bounding box tối đa80 phần tử, không thực thi JS tùy ý của model. Không thực thi Python/JavaScript/shell tùy ý do model sinh ra, không có tool upload file local. Navigation bị giới hạn cùng origin với URL người dùng đưa vào; private network bị chặn. Call ID trùng trả cache, không tự click lại. Lỗi có thể đã có thao tác thành công trước đó nên model được yêu cầu kiểm tra trước khi thử lại.

Khi đã thấy một đoạn text chứng minh thành công, Copilot gọi `export_project` với tên và đoạn text đó. Harness kiểm tra text đang có trên trang rồi xuất ZIP riêng gồm `run.py`, `playwright_runtime.py`, `actions.json`, `requirements.txt`, `README.md`, `evidence.json` có thời gian/assertion và ảnh `evidence.png` chụp ngay lúc kiểm tra thành công. Ảnh cũng được lưu riêng bên ngoài ZIP. Project chạy lại bằng **Python Playwright**, không cần Copilot/Frida. Project xuất ở challenge sau có thể chứa các bước tiền đề đã làm từ đầu session. Việc xác nhận chỉ dựa trên assertion cụ thể của lần chạy, không mặc nhiên chứng minh mọi challenge đã được giải.

Artifacts và trace được lưu trong conversation. Tool result dài được lưu JSON rồi upload một attachment để Copilot đọc. Web `/browse` và CLI `workflow` giữ browser giữa các lượt, pause, approval và sau kết luận để bạn iterate. Đủ **20 lượt model**, trạng thái chuyển sang **Chờ bạn cấp thêm lượt**; không có lượt 21 cho đến khi bạn bấm **Cấp thêm 20 lượt** hoặc đồng ý ở CLI. Lượt sửa JSON cũng tính vào ngân sách. Pause có hiệu lực tại ranh giới thao tác/lượt; không hủy prompt đã gửi. **Đóng browser** kết thúc session nhưng giữ project và artifacts.

Lệnh CLI `browse` cũ vẫn dành cho script tương thích và đóng browser khi kết thúc ngân sách; dùng `workflow` cho luồng mới có khôi phục và cấp thêm lượt. Sau backend restart, DOM cũ không thể phục hồi: harness yêu cầu bạn kiểm tra Teams rồi xác nhận **Khôi phục**. Nó mở DOM mới ở URL cuối, không replay click/submit cũ và không tự gửi lại prompt chưa xác nhận hoàn tất. Không dùng luồng tự động cho thao tác giao dịch khi chưa bổ sung duyệt hành động phù hợp.

Giới hạn hiện tại: tối đa 30 actions/call, 100 dòng XLSX, 1.500 actions/session; chưa xử lý iframe, CAPTCHA, OCR, kéo thả, phiên đăng nhập có sẵn hay mọi loại challenge. Tài liệu giao thức đầy đủ nằm trong `playwright_tool.py`; kết quả kiểm thử trực tiếp trong `playwright-tool-validation-result.json`. Vòng kiểm thử live Input Forms hoàn tất sau 10/20 lượt: Copilot tự yêu cầu tool, xử lý lỗi selector, đạt 100% (70/70 trường), xuất ZIP, và ZIP chạy lại trong browser mới vẫn đạt 100%. Chưa kiểm chứng các challenge khác. Runtime được kiểm thử riêng trong `playwright-runtime-validation-result.json`.

Alias `copilot.cmd` vẫn được giữ cho script cũ; tên chính là `nopilot`.

## 10. Dev workspace và vòng lặp có người duyệt — đã triển khai

Mở **⌘ Dev** để xem project, explorer, yêu cầu duyệt và log. Trên thẻ ZIP chọn **⌘ Xem ZIP** → kiểm tra cây file/hash → giải nén thành project mới. Không có file nào được chạy khi kiểm tra hoặc giải nén.

Chọn file trong project để đọc/sửa; lưu tạo checkpoint trước thay đổi và hiển thị diff. Có thể so sánh/rollback checkpoint, mở folder hoặc xuất ZIP. Checkpoint là bản sao có manifest, không yêu cầu Git. Project và artifacts riêng theo conversation.

Copilot có các tool `project.list/create/read/write/diff/inspect/extract/propose_run`. `export_project` tự nhập ZIP replay vào workspace để tiếp tục sửa. Model chỉ **đề xuất** install/run: màn hình duyệt hiển thị mã nguồn, revision, argv, cwd, timeout, dependency và việc log sẽ được gửi lại Copilot nếu thuộc vòng explorer. Bạn kiểm tra source đầy đủ, tick xác nhận rồi **Duyệt một lần**, hoặc **Từ chối**. Không có tool cho model tự approve, execute hay cấp lượt. Sửa source làm approval cũ mất hiệu lực; approval hết hạn sau 15 phút, chỉ dùng một lần.

Runner tạo bản sao riêng của đúng source được duyệt tại `approved-sources/<approval-id>` rồi chạy ở đó. File mới/thay đổi được thu về artifacts; muốn đưa kết quả trở lại source cần sửa/nhập có chủ đích. Cài dependency và chạy code là hai lần duyệt riêng. Log stdout/stderr hiện trực tiếp trong Dev panel, có nút **Dừng cả cây process** và **Mở thư mục lượt chạy**. Venv chỉ tách package; chương trình vẫn có quyền Windows của bạn. Không truyền token/cookie Teams hay toàn bộ environment của backend sang chương trình.

Các lệnh CMD độc lập:

```bat
nopilot.cmd dev inspect "C:\work\project.zip"
nopilot.cmd dev --data-dir "C:\work\dev-data" extract "C:\work\project.zip"
nopilot.cmd dev --data-dir "C:\work\dev-data" list
nopilot.cmd dev --data-dir "C:\work\dev-data" install PROJECT_ID requirements.txt --timeout 600
nopilot.cmd dev --data-dir "C:\work\dev-data" run PROJECT_ID run.py --timeout 120
nopilot.cmd workflow --data-dir "C:\work\nopilot-workflow" list
nopilot.cmd workflow --data-dir "C:\work\nopilot-workflow" resume TASK_ID
```

`dev` yêu cầu gõ chính xác `RUN <8-ký-tự-id>` sau khi xem kế hoạch. Không truyền `--yes` hoặc quyền tự duyệt. `workflow resume` yêu cầu `RECOVER <8-ký-tự-id>` sau khi kiểm tra Teams. Các option của `dev/workflow` đặt ngay sau tên lệnh, trước `start/run/...`. Thư mục dữ liệu CLI dev độc lập với Web; không trỏ dev CLI vào root dữ liệu Web. Chỉ một process được giữ lock trên cùng data-dir.

Mở UI không cần attach Teams ngay:

```bat
nopilot-web.cmd --offline --data-dir "C:\work\nopilot-data"
```

Đọc [DEV_WORKFLOW.md](DEV_WORKFLOW.md) để xem cấu trúc lưu trữ, giới hạn và cách kiểm thử. Bộ test lặp lại nằm trong `tests/`. Phiên live mới đã replay Input Forms đạt **100%**, cài dependency sau duyệt, sửa README có checkpoint và dừng đúng 20/20; trạng thái kết luận Copilot xem trong `live-iterate-validation-result.json`. Các challenge khác chưa được xác nhận.

## Kiểm thử nhiều challenge ngày 24/10

Đã gửi prompt qua nopilot và Copilot thật cho cả 5 challenge. Sau 20/20 lượt: Input Forms đạt 100%, có ảnh và JSON bằng chứng; 4 bài khác chưa hoàn thành. Movie Search trả resource unavailable; Invoice Extraction bị policy cùng origin của harness chặn; Shortest Path cần khám phá thêm DOM bản đồ; Stock Market chưa xác định tiêu chí hoàn thành. ZIP export trong phiên này chưa replay được vì còn selector ngẫu nhiên từ lần thử lỗi. Đây là kết quả dở dang, chưa chứng nhận hoàn thành mọi bài. Bộ bằng chứng riêng nằm trong rpa-challenges-evidence.zip cạnh gói nopilot.zip.

## Bổ sung cho phiên tiếp tục sau khi cấp lượt

Sau grant/iterate/recover hoặc sửa JSON sai schema, harness gửi lại giao thức đầy đủ và snapshot hiện tại để không phụ thuộc hoàn toàn vào bộ nhớ chat của Copilot. Lượt sửa lỗi vẫn tính trong ngân sách, không tự tăng lượt. Recovery reset bộ đếm sửa schema sau khi đã được xác nhận.

`read_resource(url)` đọc text công khai cùng origin (JS/JSON/CSV), không chạy script và không theo redirect. `upload_csv(selector,content)` chỉ ghi CSV từ text trong request rồi gắn vào file input của trang; không nhận đường dẫn file local. `browser.bundle_downloads` chỉ nén các file đã download trong browser session thành ZIP mang đuôi TXT, tối đa1MiB, rồi đính kèm cho Copilot.

API điều phối `open_url` tạo context sạch tại URL được người điều khiển chọn, giữ nguyên tổng budget và reset history replay/tables cho context mới. Model không có tool tự gọi API này. Mỗi context vẫn giới hạn origin riêng; không nới quyền navigation cho model. Đây là API điều phối, chưa có nút chọn URL mới trong Dev panel.

Sau đợt được cấp thêm20 lượt: đã dừng40/40. Invoice Extraction đã truy cập và tải một phần hóa đơn, chưa được chấm thành công. Input Forms có bản replay đã sửa trace từ các bước Copilot thực hiện thành công; chạy trong browser mới đạt100%, exit0. Bộ bằng chứng rpa-challenges-evidence.zip lưu cả bản export lỗi cũ và bản sửa để đối chiếu. Các bài khác vẫn chưa xác nhận thắng.
## Native images và ghi dữ liệu có cấu trúc

Thẻ ảnh native trong Copilot dùng ID GUID và preview ảnh, không có dòng filename hay ID SPO như file OneDrive. Bridge nay nhận dạng ảnh đã decode, có nút remove hoạt động và không còn progress, ổn định8 lần đọc. Completion signal ghi rõ đây là heuristic preview; không khẳng định đã lưu ảnh lên OneDrive. Kiểm thử live xác nhận Copilot đọc được nội dung ảnh JPG sau khi gắn. Tối đa3attachment mỗi prompt vẫn được giữ.

`record(data,pause:true)` nhận trực tiếp JSON object/array (tối đa64KiB), lưu notes JSON và tạm dừng sau tool call để người điều phối gắn đợt ảnh tiếp theo. Không cần JSON lồng trong string nên tránh lỗi escape. Record không cấp lượt, không thực thi mã. CLI workflow khi paused vẫn giữ executor/browser và nhận `/upload "path"`, `/resume`, `/iterate task` hoặc `/quit`.

Nếu chỉ có response sai JSON đã được xác nhận chưa thực thi, API recover có tùy chọn keepBrowser:true để sửa giao thức mà giữ DOM; từ chối tùy chọn này nếu mất browser, request hợp lệ chưa rõ trạng thái hoặc tool đang dở. UI mặc định vẫn khôi phục browser mới. Assertion text chấp nhận khác biệt whitespace/xuống dòng; nội dung phải khớp, không chấp nhận marker sai.

Sau60/60 lượt: Input Forms và Invoice Extraction đã thành công. Invoice Extraction được Copilot đọc ảnh và gọi upload_csv; người phát triển kiểm tra identity ảnh và ghép dữ liệu, rồi viết project replay. Project chạy lại trong browser mới được trang xác nhận thắng trong4.379giây, exit0. Nó đọc ID/DueDate mới mỗi lần và kiểm tra SHA256 ảnh trước khi dùng catalog12ảnh cố định; ảnh thay đổi thì dừng để OCR lại. Không coi đây là OCR tổng quát. Shortest Path, Movie Search và Stock Market còn chưa được xác nhận hoàn tất. Xem bộ bằng chứng và từng project ZIP ngoài gói nopilot.


### Định dạng câu trả lời

Bridge lưu cả `answer` (văn bản gốc để tool/CLI xử lý) và `answerMarkdown` chuyển từ DOM Copilot. Web lưu bản Markdown riêng trong message `markdown`, render heading, bold/italic, lists, bảng cuộn ngang, blockquote, inline code và code block có tô màu + Copy. Whitespace code được giữ nguyên. Tin nhắn cũ vẫn đọc được từ text nhưng không khôi phục chính xác định dạng đã mất.

Thư viện markdown-it 14.1.0 và highlight.js 11.11.1 được đóng gói local trong web/vendor, có license và SHA-256 trong NOTICE.json; không phụ thuộc CDN lúc chạy. Raw HTML bị vô hiệu hóa, chỉ link HTTP(S) được bấm, ảnh ngoài chỉ hiện alt text; không biến chữ sandbox thành artifact giả. File tải về vẫn qua bridge và bảng Artifacts.


### Nhập code có sẵn và lặp vòng phát triển

Web: chọn nút **Workspace** hoặc `/workspace "C:\src\my-project"`. Card cho xem source đã lọc theo `.nopilotignore`, file bỏ qua và thư mục đích. Duyệt **Nhập workspace và lưu Git backup** để lấy bản sao được Nopilot quản lý; không sửa thư mục/repository gốc. Git backup private nằm ngoài source, không push remote. Sau đó mở source workspace để sửa local tại đúng bản đang làm việc.

Gửi `/iterate yêu cầu sửa` để tự đóng gói project hiện tại thành ZIP mang đuôi `.txt`, upload và yêu cầu Copilot trả ZIP đầy đủ theo development contract. ZIP tải được sẽ có card cập nhật/chạy: duyệt diff và commit message → backup source/Git → áp dụng snapshot → giữ venv khi dependencies còn khớp, cài khi đổi → start. Log vẫn gửi riêng qua `/upload`; mỗi vòng mới cần bạn duyệt kế hoạch mới. Đây là luồng Python, chưa hỗ trợ contract Node.js.

Tài liệu HTML đầy đủ (có ví dụ prompt, ignore, contract, thư mục, recovery) mở bằng nút **Hướng dẫn** ở đầu giao diện hoặc `http://127.0.0.1:8765/help`. Bản HTML đóng gói tại `web/help.html`, đọc được offline.
