# Kiểm thử nopilot từ UI với Copilot thật

Luồng chính để đánh giá harness/bridge là thao tác trên Web nopilot, nhận phản hồi Teams Copilot thật và kiểm tra artifact/điều khiển trên UI. Unit/API test chỉ bổ trợ. Không dùng script gọi thẳng API thay cho thao tác người dùng khi đánh giá end-to-end.

1. Mở `nopilot-web.cmd`, vào `http://127.0.0.1:8765/`, bấm **Cuộc trò chuyện mới**. Dùng conversation test riêng, giữ nguyên các phiên đang làm việc và ngân sách của chúng.
2. Gửi prompt nhiều dòng có tiếng Việt và marker riêng. Xác nhận phản hồi thật, composer gửi xong và có thể dùng tiếp.
3. Nhập `/upload "đường dẫn tuyệt đối tới file dữ liệu test"`. Không dùng file nhạy cảm. Sau khi bridge báo đính kèm, hỏi một mã chỉ có trong file để xác minh model đọc nội dung thật.
4. Yêu cầu Copilot tạo ZIP nhỏ gồm `run.py` và README. Kiểm tra ZIP được tự tải về, mở **Xem ZIP**, giải nén và đọc mã từ Dev workspace. Tạo phiếu đề xuất rồi **Từ chối** để xác minh không tự chạy. Nhánh thực thi cần người dùng xem và duyệt đúng lệnh trên UI.
5. Chọn **Playwright tool**, gửi URL công khai và tác vụ nhỏ: snapshot, diagnostics, download hai ảnh mẫu, attach_images, record_images rồi session.memory. Kiểm tra identity/nội dung OCR trên ảnh, không chỉ tin final text.
6. Khi đã kết thúc một bước và không còn request đang dở, restart backend để thử recovery. UI phải giữ số lượt cũ, yêu cầu kiểm tra trạng thái Teams, mở browser mới sau xác nhận và cung cấp memory cũ; không tự replay click/upload.
7. Export một project smoke đọc trang/download. Kiểm tra `replay-verification.json` và ảnh replay trong browser mới. Điều này không chứng minh đã giải một challenge.
8. Negative test: yêu cầu ba tool calls với selector chắc chắn không tồn tại, mỗi call một action và ID mới. Harness phải pause sau ba lỗi, UI hiện lý do. Đổi yêu cầu qua iterate để kết thúc mà không cấp thêm lượt.
9. Thử container unavailable nếu engine chưa chạy: UI phải giữ lỗi preflight và không tạo phiếu host/run thay thế.

Mỗi lượt sửa schema cũng tính ngân sách. Dừng khi hết20lượt và xin cấp thêm; không tự grant. Lưu ảnh UI, conversation test, tool trace, ZIP, replay verification và các giới hạn. Không dùng thành công của mock để kết luận bridge thật hoạt động.

## Kết quả live ngày24/10/2026

- Chat/upload/ZIP: hai phản hồi model thật, verification_code trong file được đọc đúng; ZIP344B tải về, inspect/extract/read thành công; phiếu chạy bị từ chối, không có run.
- Explorer: 16/20lượt. Hai ảnh mẫu OCR đúng8trường khi đối chiếu ảnh; identity dùng nhãn hash, không suy thứ tự. Recovery giữ memory/downloads. Fresh replay đọc/download PASS. Auto-pause đúng14/20 sau3lỗi cố ý; iterate kết thúc16/20.
- Lượt đầu model từ chối vì hiểu nhầm external tool; schema repair tự phục hồi. Đã chỉnh mô tả JSON planner, nhưng chưa đánh giá độ ổn định qua nhiều phiên mới.
- Docker engine chưa hoạt động: chưa chứng nhận container isolation end-to-end. Nhánh chạy code sau người dùng duyệt chưa được thực hiện trong phiên UI test này.
- Phiên challenge cũ vẫn60/60, kết quả2/5không thay đổi.

Gói bằng chứng riêng: `kopilot-ui-live-evidence.zip`, đặt cạnh `nopilot.zip` trong thư mục outputs của lần làm việc này. Xem thêm [RELIABILITY.md](RELIABILITY.md).
