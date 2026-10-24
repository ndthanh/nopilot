# Gửi lại dự án để Copilot sửa

Luồng này dùng được trong Web chat và CLI tương tác. Bạn tự giải nén ZIP Copilot trả về, tạo venv, cài dependencies và chạy dự án. `/project` chỉ đóng gói, upload và hỏi Copilot; không chạy code.

## Project hiện tại trong Web chat

Sau khi đã chạy project trên card, dùng `/project current yêu cầu sửa`. Nopilot lấy source hiện tại theo conversation, không lấy ZIP cũ hoặc snapshot chạy. Không cần dialog, tự nén ZIP mang đuôi TXT và upload cùng yêu cầu. Có thể gõ `/project c` rồi Tab. Nếu chưa có active project, chỉ dùng project duy nhất đã được chấp thuận trong conversation; nếu có nhiều project hoặc project đang chỉ ở trạng thái chờ duyệt, báo lỗi và yêu cầu chỉ định đường dẫn. CLI vẫn dùng đường dẫn tuyệt đối.

```text
/project current Thay URL bằng https://facebook.com, lưu screenshots/facebook.png, giữ dependencies, bỏ previewUrl và trả ZIP đầy đủ cùng nopilot.json và commit message.
```

Lệnh này không tự gửi log hoặc output của lần chạy. Có thể thêm `--exclude "screenshots/**"` trước yêu cầu, hoặc khai báo trong `.nopilotignore`.

## Copilot trả đường dẫn chữ nhưng thiếu link tải

Gửi tin nhắn thường trong cùng conversation, chưa cần đóng gói/upload lại:

```text
Bạn vừa trả đường dẫn sandbox dạng văn bản nên tôi chưa tải được file. Hãy dùng công cụ tạo file để tạo lại ZIP đầy đủ của dự án đã sửa, kiểm tra file thực sự tồn tại và đính kèm file tải được. Trả link Markdown bấm được: [Tải dự án](sandbox:/mnt/data/facebook_playwright_edge_project.zip). Giữ nopilot.json, README, .nopilotignore và NOPILOT_COMMIT_MESSAGE.txt; không chỉ mô tả thay đổi hoặc in đường dẫn. Nếu không thể tạo/đính kèm file trong phiên này, hãy nói rõ, không bịa link.
```

Markdown chỉ là định dạng link, không chứng minh ZIP tồn tại. Nopilot chỉ hiện card khi bridge tải được file thật. Nếu file hết hạn hoặc model không còn source, dùng lại `/project current` cùng yêu cầu để gửi source hiện tại.

## Ví dụ trong chat

```text
/upload "C:\work\my-app\logs\start-failed.log"
/project "C:\work\my-app" Hãy đọc log đính kèm, tìm nguyên nhân, sửa mã nguồn và trả lại ZIP cùng hướng dẫn chạy bằng CMD.
```

Log vẫn chọn bằng file dialog khi hoàn thành `/up` bằng Tab, hoặc nhập đường dẫn tuyệt đối. Không có bước tự thu thập log. Có thể bỏ `/upload` nếu chỉ yêu cầu sửa tính năng.

Harness giữ các attachment đang chờ; project dùng thêm một slot. Tối đa3file mỗi lượt, nên có thể đính kèm tối đa2log trước `/project`.

## Bỏ thư mục và file nặng

Đặt file UTF-8 `.nopilotignore` ở **gốc dự án**. File này thay thế toàn bộ bộ ignore mặc định, nên hãy bắt đầu bằng cách copy file mẫu `.nopilotignore` đi kèm Nopilot:

```bat
copy "C:\tools\nopilot\.nopilotignore" "C:\work\my-app\.nopilotignore"
```

Sau đó sửa file, ví dụ:

```gitignore
# Không gửi môi trường, dependencies và dữ liệu tạm
.venv/
node_modules/
logs/
*.log
*.zip
.env
/data/
**/cache/
*.tmp
!important.tmp
```

Hỗ trợ comment `#`, dấu `*`, `?`, `**`, `/` neo tại gốc, `/` cuối dòng cho thư mục, và `!` để đưa file trở lại. Quy tắc sau ưu tiên hơn quy tắc trước. Để đưa một file trở lại, thư mục cha của nó phải không bị loại: dùng `data/*` rồi `!data/keep.txt`, thay vì loại toàn bộ `data/`. Pattern dùng `/` cả trên Windows và phân biệt hoa/thường. Chỉ đọc `.nopilotignore` ở gốc, chưa đọc file ignore lồng nhau; không tự dùng `.gitignore`.

Nếu dự án chưa có `.nopilotignore`, Nopilot dùng file mẫu mặc định trong thư mục cài đặt; không tự ghi file vào dự án. Mẫu mặc định bỏ venv/dependencies/cache/build/log/archive và các tên secret thông dụng. Khi có file riêng, bạn kiểm soát hoàn toàn những quy tắc này. Symlink/junction luôn bị bỏ qua độc lập với ignore.

Chat hiển thị file quy tắc đã dùng; manifest lưu nguồn, SHA-256 và số pattern. File `.nopilotignore` cũng được gom vào source trừ khi chính quy tắc loại nó.

`--exclude` vẫn dùng được để loại thêm theo glob cho riêng một lượt (không hỗ trợ `!`, không ghi lại file ignore):

```text
/project "C:\work\my-app" --exclude "data/**" --exclude "*.tmp" Hãy sửa lỗi và giữ nguyên API hiện tại.
```

Đường dẫn có dấu cách phải đặt trong dấu nháy. Câu hỏi có thể nhiều dòng. Mỗi lượt đóng gói tạo artifact riêng và manifest SHA-256; không sửa thư mục nguồn.

Web chat hiển thị các bước: chuẩn bị → số file/kích thước/thời gian và các mục bỏ qua → upload TXT → attachment sẵn sàng → chờ Copilot. File được tạo trực tiếp bằng byte ZIP với tên `.txt`, không qua bước sao chép ZIP rồi đổi tên. ZIP dùng mức nén3 để giảm thời gian CPU.

Giới hạn bridge hiện tại: archive1MiB, tổng source16MiB,2000file. Nếu quá giới hạn, thêm `--exclude` hoặc chia dự án; harness báo lỗi thay vì gửi thiếu âm thầm. Với dự án lớn, mỗi lần vẫn đóng gói toàn bộ source còn lại, chưa có upload incremental.

Copilot được hướng dẫn mở byte ZIP thật, đọc manifest/source/log đã đính kèm. Nếu chỉ nhận source đã trích xuất, nó vẫn được sửa/tạo ZIP mới nhưng phải nói rõ chưa xác minh archive gốc; nếu thiếu source cần thiết phải nêu file thiếu hoặc `ACCESS_UNAVAILABLE`. Kiểm tra câu trả lời và mã sửa trước khi chạy lại.

## Kiểm thử thực tế 24/10/2026

Đã yêu cầu tạo Flask ZIP từ Web UI nopilot; kiểm tra source, giải nén, tạo venv/cài Flask và chạy `start.cmd` thủ công bằng CMD. Sau khi cố ý tạo JSON lỗi, upload log riêng rồi gọi `/project` từ UI; Copilot trả marker mới chỉ có trong source upload và ZIP sửa. Bản cuối chạy lại thành công: trang chủ `KopilotDevLoop`, `/api/add?a=2&b=3` trả `{"sum":5}`.

Hai lần pack mất0,031s/0,023s, archive1850/1835byte; bỏ qua khoảng50,7MB trong `.venv`, `node_modules`, `logs` (gồm32MiB fixture kiểm thử). Đây là thời gian pack source nhỏ sau loại trừ, không bao gồm thời gian upload/chờ model và không đại diện dự án lớn. Lần đầu gặp `ACCESS_UNAVAILABLE` do prompt bắt xác minh archive nhị phân; đã sửa fallback source trích xuất và kiểm thử lại `/project` thành công không cần nhắc thêm. Bộ test79:78pass,1skip integration cài package; việc pip install thật đã được kiểm tra riêng trong scenario này.

Bằng chứng riêng: `kopilot-project-loop-evidence.zip` bên cạnh gói phát hành, chứa transcript, manifest, ZIP trước/sau, log và ảnh UI. Chưa thử lại native path dialog trong scenario này; upload log dùng đường dẫn nhập tay.
