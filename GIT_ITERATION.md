# Iterate bằng ZIP, giữ venv và lưu Git local

**Luồng chính hiện tại:** dùng card Chạy thử ngay trong chat, đồng ý một lần cho kế hoạch cài/chạy. Xem [CHAT_FLOW.md](CHAT_FLOW.md). Các hướng dẫn thao tác từng bước dưới đây dành cho khu vực Nâng cao/CLI.


## Cách dùng

1. Dùng `/develop ...` để yêu cầu project đầu tiên. Nopilot yêu cầu Copilot kèm `NOPILOT_COMMIT_MESSAGE.txt` trong ZIP; khi `/project` yêu cầu sửa, prompt cũng nhắc trả snapshot source đầy đủ và message mới.
2. Nhập ZIP đầu tiên như trước, duyệt cài/chạy/check. Venv nằm ngoài source, thuộc project này.
3. Khi cần sửa, dùng **Soạn yêu cầu sửa**. Upload log riêng bằng `/upload` nếu cần; sau đó gửi `/project`. Copilot trả ZIP snapshot mới và commit message.
4. Trên ZIP mới: **Chuẩn bị dự án → Hoặc cập nhật project hiện có → chọn project → Xem diff**. Chưa áp dụng source và chưa chạy mã.
5. Kiểm tra project đích, đường dẫn, revision, danh sách added/modified/deleted và diff. File không có trong ZIP sẽ bị xóa khỏi source: đây là snapshot đầy đủ, không phải ZIP patch. Message được đọc từ `NOPILOT_COMMIT_MESSAGE.txt`; bạn có thể sửa trước khi dùng. Nếu file thiếu/sai, nhập message thủ công.
6. Tick đã xem diff → **Áp dụng ZIP + commit local**. Nopilot lưu checkpoint và trạng thái source trước cập nhật, thay source, commit bản mới. Project ID, venv, lịch sử run vẫn giữ. Review cũ bị từ chối nếu source/staging thay đổi, đã apply, hoặc quá15phút.
7. Nếu dependencies khớp, chạy/check ngay qua phiếu HITL mà không cần pip/venv lại. Code mới vẫn cần duyệt lệnh; việc giữ venv không cấp quyền tự chạy mã.

Vẫn có lựa chọn giải nén ZIP thành workspace mới nếu muốn tách hẳn phiên bản. Cách đó tạo project/venv riêng.

## Khi nào dùng lại venv?

Sau một lượt cài root `requirements.txt` thành công, Nopilot ghi receipt ngoài source. Receipt gắn với:

- Các dòng pin `package==version`, sắp xếp và bỏ comment/dòng trống.
- Python host: phiên bản và SHA-256 executable.
- Registry cố định PyPI và SHA-256 executable Python trong venv.

Chỉ sửa source/README/args không làm mất receipt. Chỉnh comment hoặc thứ tự requirements cũng không bắt cài lại. Không chia sẻ venv giữa các project hoặc conversation.

Nếu pins/Python/runtime đổi, UI yêu cầu duyệt cài. Khi duyệt, venv cũ được **di chuyển** vào `environment-backups/APPROVAL_ID/venv`, receipt cũ đi cùng; sau đó tạo venv sạch và cài dependencies. Không tái sử dụng packages đã bị bỏ khỏi requirements. Backup được giữ để bạn kiểm tra, chưa tự xóa.

Mọi lần cài đều vô hiệu receipt cũ trước khi pip chạy. Cài thất bại không ghi receipt thành công; cần duyệt cài lại. Receipt mới chỉ ghi sau khi cài thành công. Receipt không kiểm tra từng file trong site-packages; nếu sửa packages bằng tay, hãy chủ động cài lại. Dự án cài bằng bản Nopilot cũ chưa có receipt cần cài một lần để ghi nhận; venv đã có nhưng không có receipt sẽ được backup trước khi tạo lại.

## Git lưu ở đâu?

```text
dev/projects/PROJECT_ID/
  source/                     # source bạn sửa và đóng gói
  venv/
  environment.json            # receipt cài dependencies
  environment-backups/
  git-worktree/.git/          # repository local riêng do Nopilot quản lý
  checkpoints/
  updates/REVIEW_ID/          # ZIP đã stage và bản review
```

Git mirror nằm ngoài source nên không lọt vào `/project`, ZIP export hoặc runtime snapshot. Không khởi tạo repo Git trong source. ZIP có `.git` bị từ chối.

Nopilot dùng Git có trong PATH, không cần remote và không push. Author commit là `Nopilot <nopilot@localhost>` qua cấu hình riêng từng lệnh, không thay Git config toàn máy. Git hooks và ký commit bị tắt cho repository do harness quản lý. Commit message được truyền bằng file, không ghép vào shell command.

Trong **Git local của project**, chọn **Xem lịch sử / lấy message Copilot**, hoặc tự nhập message rồi **Commit source hiện tại**. Khi apply ZIP, nếu source hiện tại chưa có commit hoặc có thay đổi local, Nopilot ghi thêm commit checkpoint trước commit mới của Copilot. Nếu Git commit sau cập nhật lỗi, harness khôi phục source từ checkpoint và báo lỗi; không chạy dự án.

Diff là so sánh source hiện tại với toàn bộ ZIP mới, chưa có three-way merge hay resolve conflict tự động. Local edit vẫn hiển thị trong diff và có checkpoint/commit lưu lại trước khi thay. Không tự biết những file bị Copilot bỏ quên có phải xóa có chủ đích hay không: bạn cần xem danh sách deleted.

## Kiểm thử 24/10/2026

- UI thật: gửi source máy tính qua `/project`, nhận ZIP sửa và commit message do Copilot viết, xem diff, apply vào project cũ, xem lịch sử Git. Commit mới: `feat: support uppercase X and Vietnamese operator words`.
- Integration riêng bằng runner và package `colorama` từ PyPI: cài bản0.4.6, chạy source cũ, apply source mới có cùng pins, xác nhận hash/mtime venv không đổi và lượt run không có bước tạo venv/pip. Đổi pin sang0.4.5, duyệt cài, xác nhận venv cũ được backup và môi trường mới cài thành công.
- Unit test kiểm tra stale review, apply một lần, message có ký tự shell, ZIP có `.git`, đổi requirements/runtime, cache tồn tại qua restart và rollback khi Git lỗi trong chuyển đổi file/thư mục.
- Bằng chứng nằm trong `nopilot-git-validation.zip` cạnh gói phát hành.
