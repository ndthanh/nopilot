# Chạy dự án ngay trong chat

Luồng chính chỉ có một card ở dưới ZIP Copilot trả về. Không cần mở khu vực Nâng cao.

## Dự án đầu tiên

1. Nhập yêu cầu qua **Tạo dự án** hoặc `/develop ...`. Copilot trả ZIP có `nopilot.json`.
2. Nopilot đọc contract bằng Python và hiện card **Bạn muốn chạy thử dự án này?**. Việc đọc/chuẩn bị chưa cài packages, chạy code hay sửa project đang dùng.
3. Card tóm tắt dependencies, entrypoint, args và timeout. Mở **Xem kế hoạch** nếu muốn xem thêm; commit message có thể chỉnh ở đây.
4. Bấm **Đồng ý cài và chạy** (hoặc **Chạy thử** nếu không cần cài). Một lần đồng ý cho đúng phiên bản và chuỗi tác vụ đã hiển thị: ghi Git local → tạo venv/cài dependencies nếu cần → chạy entrypoint. Không cần xác nhận lại từng bước trong cùng chuỗi.
5. Card hiện tiến trình, **Xem log**, **Dừng**, và **Mở ứng dụng** nếu web app đang chạy có URL trong contract. URL là khai báo của project, chưa phải kiểm tra health.

Nếu chưa muốn chạy, bấm **Để sau**. Chuẩn bị card không gọi thêm LLM; chuỗi chạy hoàn toàn dựa trên contract và code local.

## ZIP cập nhật

Sau khi đã dùng một project trong conversation, ZIP tiếp theo mặc định cập nhật project đó. Với conversation cũ có đúng một project, Nopilot cũng chọn project đó. Card ghi rõ **project đích** và cho chọn **Tạo project riêng** nếu đây là dự án khác.

1. Mở **Xem kế hoạch và diff** để kiểm tra file thêm/sửa/xóa và commit message Copilot viết.
2. Bấm **Cập nhật và chạy**. Nopilot lưu source hiện tại vào Git trước, áp dụng toàn bộ ZIP vào cùng project, commit bản mới, dùng lại venv nếu requirements/Python còn khớp, rồi chạy.
3. Nếu dependencies thay đổi, việc cài lại đã nằm trong kế hoạch được đồng ý: giữ venv cũ làm backup, tạo môi trường sạch, cài rồi mới chạy. Không cần download/cài lại khi pins không đổi.

ZIP là snapshot đầy đủ: file vắng mặt được xem là bị xóa. Nếu ZIP trùng source hiện tại, Nopilot chỉ đề xuất chạy, không áp dụng lại source. **Chạy lại** sau thành công dùng source hiện tại, không giải nén ZIP cũ đè lên các chỉnh sửa local.

## Kiểm tra và sửa tiếp

Sau khi task kết thúc, card có **Kiểm tra** nếu contract khai báo `tasks.check`, và **Yêu cầu sửa** để điền `/project "source-path" ...` vào ô chat. Hai nút chỉ chuẩn bị kế hoạch/câu hỏi; không tự gửi prompt hay chạy test trước khi bạn đồng ý.

Log vẫn giữ local. Nếu cần gửi Copilot, dùng `/upload` và chọn log, rồi gửi yêu cầu sửa như trước. Các log của từng bước cũng có trong artifacts/chat.

## Giới hạn và xử lý lỗi

- Một lần đồng ý chỉ có hiệu lực cho đúng kế hoạch: source, runtime, dependencies, args và timeout đã xem. ZIP mới cần đồng ý mới; đây không phải cấp quyền chạy mọi code trong conversation.
- Kế hoạch/diff hết hạn sau15phút. Nếu source/runtime đổi, mở chi tiết rồi **Lập lại kế hoạch ZIP**. Contract thiếu hoặc không hợp lệ thì card báo rõ; Nopilot không đoán lệnh từ README.
- Cài thất bại thì không chạy bước start. Dừng chuỗi thì không chạy bước kế tiếp. Bấm lặp một lần đồng ý không tạo hai lượt chạy.
- Backend khởi động lại đánh dấu chuỗi dở là interrupted, không tự tiếp tục hay gửi lại prompt. Bạn cần xem trạng thái và đồng ý một kế hoạch mới.
- Python, task tối đa600giây, stdin đóng; CLI dùng args hoặc giao diện web. Mã chạy với quyền Windows hiện tại. Không có tự động push Git hay tự gửi log.
- **Nâng cao** giữ editor, checkpoint, Git và điều khiển chi tiết cho trường hợp cần thiết. Luồng Dev từng phiếu duyệt trong CLI/Nâng cao vẫn dùng được.

Contract vẫn là [nopilot.schema.json](nopilot.schema.json), không cần LLM tham gia vào bước cài/chạy. Xem [GIT_ITERATION.md](GIT_ITERATION.md) cho cache môi trường và Git.

## Kiểm thử bản này

UI thật đã hiển thị card cho ZIP có contract, xác nhận tái sử dụng venv, giữ form ổn định khi polling, mở/đóng chi tiết, chọn Để sau và xem lại mà không chạy mã. Không bấm tự đồng ý chạy code Copilot trên UI; card được để sẵn cho người dùng thử.

Integration riêng dùng source fixture biết trước và colorama từ PyPI: một lần đồng ý tự cài rồi chạy; một lần đồng ý cập nhật source cùng pins dùng lại venv rồi chạy; một lần đồng ý đổi pin backup/cài môi trường mới rồi chạy. Chuỗi không tạo lời gọi LLM. Unit/API tests bao phủ bấm lặp, cài lỗi không start, dừng trong khi cài, stale source/runtime, chống CSRF/cross-conversation và restart không tự tiếp tục. Bộ test110:109pass,1skip integration cài package; cài package thật đã kiểm tra riêng như trên.

Bằng chứng nằm trong `nopilot-chat-validation.zip` cạnh gói phát hành. Một lượt chạy test ban đầu gặp Windows WinError10053 tại request HTTP kiểm tra Origin; chạy lại test bảo vệ và toàn bộ suite đều đạt, không bỏ qua assertion.


## Bắt đầu từ project local có sẵn

Dùng `/workspace "C:\src\my-project"`, duyệt card nhập bản sao source và Git backup. Dùng `/iterate yêu cầu sửa` trong cùng conversation; các bước ZIP → diff → duyệt → backup/apply → cài/run dùng lại luồng phía trên. Source làm việc là bản sao do Nopilot quản lý, không cập nhật tại chỗ thư mục gốc. Xem `web/help.html` hoặc nút Hướng dẫn để biết quy trình đầy đủ.
