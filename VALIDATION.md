# Kiểm thử bản Dev + Explorer

## Cập nhật 24/10/2026: workspace, Markdown và Git

- Regression trước các sửa cuối: 122 bài chạy, 121 đạt, 1 skip bài cài package qua mạng. Integration riêng đã thực sự cài package và kiểm tra dùng lại venv khi pins khớp, tạo môi trường mới khi đổi pins, backup local edit vào Git trước khi apply ZIP.
- Sau các sửa cuối: workspace 10/10; chat launch 8/8; runner 18 bài gồm 17 đạt + 1 skip integration mạng. Có test tái hiện decode Unicode trong subprocess và chọn đúng kế hoạch mới nhất sau restart.
- UI + Copilot thật: nhập folder có sẵn (loại .venv/logs/.env), duyệt Git backup, /iterate đóng gói source thành ZIP đuôi TXT và upload. Lần đầu Copilot thiếu file tải; nhắc xuất lại nhận ZIP thật, tự download và hiện card cập nhật. Sau human approval, main.py --name An và check.py đều exit 0; check in PASS.
- Markdown: heading, emphasis, bảng, danh sách lồng nhau, code Python/JSON có highlight/Copy; copy-paste giữ thụt lề và dòng trống; đã xem cả sáng/tối và reload. HTML không được thực thi, link nguy hiểm/ảnh ngoài bị chặn trong renderer.
- Báo cáo JSON, transcript, ảnh và ZIP minh chứng là dữ liệu QA local, được loại khỏi repository bởi .gitignore. Các kết quả dưới đây ghi lại các mốc thử nghiệm trước đó.

- 35/35 test core/API/explorer qua: ZIP/path, revision, checkpoint/rollback, approval một lần/hết hạn/từ chối, immutable source, stdout/stderr, environment, timeout/log cap, stop descendants, dependency install, recovery, cache và boundary 20 lượt.
- Bộ test portable mặc định: 35 test, 34 qua + 1 bỏ qua phần cài package mạng. Kiểm thử integration riêng đã cài colorama==0.4.6 và import thành công.
- Edge thật + model giả lập: giữ DOM giữa lượt 20→grant→21, iterate tiếp cùng browser.
- UI: ZIP inspect/extract, đọc/sửa/diff, nút duyệt bị khóa trước review, log, dừng process đang chạy, cấp20→40 bằng nút, draft giữ nguyên qua polling.
- CLI: inspect/extract/list offline; từ chối không chạy; duyệt bằng chuỗi RUN đúng ID chạy fixture; workflow list offline.
- Copilot thật: giải Input Forms 100%, export/import ZIP, sửa README có checkpoint, đề xuất install/run, replay project trong runner đạt100%, exit0. Đã dừng đúng20/20; chờ người dùng cấp lượt để gửi log lại và nhận final mới. Báo cáo live giữ passed:false cho đến khi nhận final, không coi thiếu grant là hoàn tất.

Reviewer của kiểm thử tự động chỉ chấp thuận fixture đã biết hoặc replay wrapper/runtime khớp hash mã harness. Sản phẩm không có cơ chế tự duyệt code model. Chưa kiểm chứng challenge khác. Xem dev-validation-summary.json và live-iterate-validation-result.json để phân biệt test mô phỏng/Edge thật/Copilot thật.
