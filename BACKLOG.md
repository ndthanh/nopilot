# nopilot backlog

Đã có: Web/CLI; URL→Markdown; Playwright JSON tool; project ZIP; ZIP inspect/extract; editor/checkpoint/diff/rollback; human approval cho install/run; immutable source snapshots; logs/outputs/stop process tree; pause/iterate; dừng 20 lượt và xin grant; recovery có xác nhận sau restart.

Còn lại:
- Kiểm chứng container end-to-end khi Docker Linux engine hoạt động; custom image có dependency/browser, export outputs và toolchain ngoài Python. Mode container hạn chế đã có, không fallback host.
- Duyệt từng thao tác browser có tác động bên ngoài, chính sách origin theo nhiệm vụ.
- Iframe, kéo thả; OCR tổng quát có đánh giá độ chính xác. Native image batch có nhãn/hash đã có; trường OCR vẫn cần kiểm tra.
- Project replay tối thiểu theo checkpoint thay vì chứa tiền đề từ đầu session.
- Tìm kiếm lịch sử, liên kết project với nhiều conversation. Checkpoint tóm tắt và session.memory đã có.
- Khôi phục conversation đã ẩn ngay trong UI.
- Search không API key với provider ổn định; không vượt CAPTCHA.
- Đánh giá độ bền bridge qua nhiều bản Teams/WebView2 và session dài.
