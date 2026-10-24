# Lời nhắn cho Copilot — ITC Save as discovery

Bạn đang hỗ trợ kiểm thử bản `agent.js` + `flow_test.py` mới cho ITC/Qt3. Mục tiêu là loại phụ thuộc menu ID cố định trong bước **report hoàn tất → File > Save as của cửa sổ con → Select file**. Không mang log ra ngoài; đọc và phân tích ngay trên máy công ty.

## Trạng thái thật của bản bàn giao

- Hai file runtime độc lập: `agent.js` và `flow_test.py`; không cần file JS/Python phụ trợ.
- Dùng config.xlsx và môi trường Frida/openpyxl hiện có cạnh runner. `ITC_EXE` là bắt buộc; `ITC_USERNAME`/`ITC_PASSWORD` cần khi dùng `x` hoặc `l`. `ITC_EXPORT_PATH` chưa được dùng để ghi file trong build discovery này.
- Phần Connect/Login/Batch/On-hold/Filter lấy từ source đã chạy được do người dùng cung cấp. Phần này vẫn có các giả định riêng của build cũ; không coi nó đã được harden hoàn toàn.
- Đã bỏ đường Save chọn bằng `-355`, đọc `QMenuItem + 0x20`, fingerprint theo thứ tự/thời gian và việc bỏ qua destroyed. Không có fallback quay về những cách này.
- Bản này đã qua syntax và tests bằng Frida mocks. **Chưa được chạy trên ITC/Qt DLL thật** tại môi trường phát triển; khả năng tương thích phải được kiểm chứng ở máy test.
- Source gốc tham chiếu: agent SHA-256 `2ac0783539dba6f857b165d88beb39ff468c69e0787fd89802a82dea4a80b235`; runner `51f2db50e7f7ba2b49a7035dc4ded60a43001a759f19a7b4090f901d59e479ea`.

## Quy trình kiểm thử được người dùng thống nhất

1. Backup hai file cũ. Chép đè hai file mới vào thư mục automation **trên test**, cạnh config.xlsx.
2. Chạy bằng Python/venv đã dùng với ITC: `python flow_test.py`.
3. Dùng `x` để chạy luồng hiện có đến Filter Enter; hoặc đưa app tới đó bằng luồng riêng đang hoạt động. **Tự chờ report thực sự hoàn tất**. `PRE_SAVE` chỉ báo đã submit filter, không chứng minh report đã hoàn tất.
4. Nhập `i` để lưu đường dẫn module và hash file thực tế.
5. Nhập `h`. Phải nhận `ok: true` và event `sl_armed`.
6. Quay lại đúng cửa sổ report, bấm tay **File > Save as...**. Quan sát `Select file`, rồi **Cancel**. Không nhập path/OK trong lượt học.
7. Nhập `j`. Runner kết thúc lượt học và lưu discovery JSON/TXT. Kỳ vọng một `UNIQUE_CANDIDATE`, `mapping_live: true`, `verified: false`.
8. Nhập `m`. Script queue việc mở lại Select file qua QSignal đã học. Khi hiện dialog, kiểm tra đúng dialog rồi **Cancel bằng tay**.
9. Nhập `j` lần nữa. Chỉ sau khi native call trả về với đúng hậu điều kiện mới kỳ vọng `verified: true` và command `completed`.
10. Thử `m` thêm một lần nếu cần. Sau đó đóng/mở lại report: mapping cũ phải bị từ chối; dùng lại `h → bấm tay → Cancel → j → m → Cancel → j` để tìm lại object trong lifetime mới.

Nếu đã đưa report tới trạng thái mong muốn bằng luồng riêng, có thể dùng ngay `h`; không cần chạy lại `x`.

`j` chỉ hoàn tất khi dialog đã đóng. Nếu còn Select file hoặc replay modal đang chạy, script yêu cầu Cancel trước.

## Cơ chế mới: học từ kết quả trong cùng phiên

Code theo dõi constructor/destructor QObject và QSignal để có reference `{address, generation, type}`. QSignal còn được gắn với lifetime QObject base quan sát được; địa chỉ trùng không được xem là cùng object.

Khi QSignal `activate()`, `intSignal(int)` hoặc `signal(const QVariant&)` thực thi, script giữ frame theo **thread + call token**, có object/generation và backtrace. Hook `onLeave` bỏ đúng frame. Giá trị integer có thể được ghi vào log nhưng không dùng làm selector.

Khi gặp caption `Select file`, hoặc exec/show của một dialog đã có caption đó, script chụp các QSignal **còn active trên cùng thread**. Nó không quét stack để đoán object và không lấy ECX của setCaption làm trigger.

Lượt học được pin vào đúng một QObject còn sống có caption `List of authorization transactions`. Nếu có nhiều report cùng caption, script trả `REPORT_OWNER_NOT_UNIQUE`, không chọn object đầu tiên.

Một signal chỉ đủ điều kiện candidate khi:

- QSignal và report có lifetime quan sát còn live;
- Select file có QObject parent chain chứa đúng report đã pin;
- Có connection từ signal tới receiver nằm trong report, hoặc chuỗi signal→signal dẫn tới receiver thuộc report;
- Thread khớp GUI thread hiện agent đang theo dõi;
- Lifecycle/connection hooks cần thiết đã được cài, không có lỗi/giới hạn làm suy giảm capture.

Lượt học còn cần bằng chứng dialog có exec/show, input nối tới `edFileNameTextChanged(const QString&)`, và nút text OK nối tới `accept()` của đúng dialog.

Nếu có **hai QSignal khác nhau** cùng đủ điều kiện, kết quả là `AMBIGUOUS_SIGNALS`. Không chọn theo thứ tự stack, pointer, integer hoặc độ gần thời gian. Các frame activate/int/variant của **cùng một QSignal lifetime** được gộp lại thành một candidate.

Lượt học thủ công chỉ tạo candidate. `m` revalidate lifetime/connection tại lúc queue và ngay trước native call trên GUI thread. Native wrapper được bind bằng profile zero-argument: `void QSignal::activate()`, `thiscall`, đối số chỉ có `this`. Không truyền integer menu ID.

Trong replay, script chỉ ghi nhận hậu điều kiện khi đúng signal đó lại dẫn tới Select file thuộc cùng report và đúng form. Native call thường chưa return cho tới khi Cancel dialog modal. `verified` chỉ được đặt sau khi call return thành công và đã có hậu điều kiện. Việc gán mapping RAM không tự được coi là thành công.

Mapping chỉ dùng trong **process/lifetime hiện tại**. Không đọc lại pointer từ JSON để invoke sau restart, không mang pointer/ID từ test sang prod. Khi report/object bị hủy hoặc connection thay đổi phải học lại.

## Các file log cần đọc

Mỗi lần chạy có thư mục mới `captures/YYYYMMDD-HHMMSS-xxxxxxxx/`:

- `events.jsonl`: tất cả Frida messages/structured events, lỗi, lệnh operator, timestamp UTC/monotonic và host sequence. Console chỉ rút gọn event của luồng cũ; event `sl_*` được in đầy đủ.
- `modules-*.json`: PID, EXE đang load, tất cả qt-mt.dll, module base/path/size và SHA-256 EXE/Qt DLL **trên đĩa**. Đây không phải hash memory image.
- `discovery-*.json`: bản đầy đủ để phân tích hook coverage, sample, candidate, owner chain, route và command.
- `discovery-*-compact.json` và `.txt`: tóm tắt để đọc nhanh.

Không log mật khẩu hoặc nội dung QLineEdit. Tên object, caption, tên slot và đường dẫn module có thể chứa thông tin nội bộ; giữ log tại máy công ty.

## Thứ tự đọc kết quả

1. **Module trước:** EXE đúng bản test/prod dự định chưa? Qt DLL ở C hay D? Có nhiều qt-mt.dll cùng tên không? Agent từ chối tự chọn khi có nhiều module Qt trùng tên. So sánh hash file giữa các bản.
2. **Hook capability:** `sl_ready.capabilities`; trong report xem `hooks[].label/matched/attached/names`. `REQUIRED_HOOKS_MISSING` nghĩa là profile lifecycle/connection không khớp, chưa phải không có Save as. Replay còn cần resolve đúng QSignal::activate zero-arg. `QFileDialog::ctor` chỉ là hook bổ sung, không bắt buộc vì dialog có thể là Qt custom.
3. **Lượt học:** `sl_armed → sl_signal_enter → sl_outcome_candidate → sl_sample_status → sl_learning_finished`.
4. **Mỗi candidate:** xem `reasons`, `outgoing_connections`, `receiver_routes`, `owner_chain`, `active_signals` và backtrace module/RVA.
5. **Replay:** `sl_replay_queued → sl_replay_begin → sl_replay_outcome → sl_replay_return` với cùng `command_id`. Queue thành công chưa chứng minh native call đã chạy; native return chưa chứng minh dialog đúng nếu `outcome_seen` false.

Các trạng thái:

| Trạng thái/lỗi | Điều cần điều tra |
|---|---|
| `WAITING_FORM_EVIDENCE` | Chưa thấy connection input filename / nút OK của đúng dialog; đọc connection signature và button text thực tế |
| `WAITING_EXEC_OR_SHOW` | Mới thấy caption, chưa có hook exec/show xác nhận đường hiển thị; kiểm tra tên export |
| `NO_ELIGIBLE_SIGNAL` | Xem từng `candidate.reasons`; có thể signal chưa được tạo dưới hook, handler async hoặc receiver owner khác |
| `AMBIGUOUS_SIGNALS` | Có nhiều signal đủ điều kiện; cần capture đối chứng và thêm bằng chứng phân biệt, không tự chọn một cái |
| `SIGNAL_RECEIVER_NOT_ANCHORED_TO_REPORT` | Xem `outgoing_connections[].receiver_owner_chain` và `diagnostic_connections`; ITC có thể dùng controller parent ngoài report |
| `DIALOG_OWNER_NOT_REPORT` | Caption trùng nhưng parent chain khác, hoặc attach/lifecycle profile thiếu |
| `THREAD_NOT_GUI` | So sánh thread event với `status.gui_thread`; agent cũ lấy từ notify đầu tiên, có thể cần sửa bằng bằng chứng widget thread |
| `STALE_MAPPING_RELEARN` | Đã đóng/tạo lại object/report hoặc tái sử dụng địa chỉ; dùng h học lại |
| `LEARNED_ROUTE_CHANGED` | Connection cũ không còn phù hợp hoặc sample không còn unique |
| `WAKE_POST_FAILED` | Chưa gửi được wake; không retry mù |
| `QUEUE_NOT_DISPATCHED` / `QUEUE_EXPIRED` | Queue không được dispatcher thực thi trong hạn; tập trung GUI message loop, không tăng delay input |
| `NO_MATCHING_SELECT_FILE_OUTCOME` | Native call đã return nhưng không có đúng Select file/form/owner; không coi replay thành công |
| `REPLAY_CAPABILITY_UNAVAILABLE` | Không resolve đủ profile activate/lifecycle; không đoán prototype khác |

`diagnostic_connections` trong report giữ tối đa 5.000 connection đang active gần nhất; cờ `diagnostic_connections_truncated` báo phần này bị cắt. Registry nội bộ giữ tối đa 30.000 object mỗi loại và 20.000 edge. Chạm giới hạn hoặc có hook error làm capture degraded và chặn replay. Tối đa 20 sample/run, gồm lượt học và replay; khi hết phải bắt đầu phiên mới.

## Việc Copilot được kỳ vọng làm tiếp

- Đọc log tại chỗ, xác định chính xác mắt xích còn thiếu.
- Nếu symbol profile chưa khớp: đối chiếu inventory/DLL đang load và xác nhận chữ ký, không lấy export đầu tiên bằng substring rồi tự suy ra đối số.
- Nếu owner chain khác: báo bằng chứng class/name/parent/connection và đề xuất ràng buộc thay thế đủ mạnh. Không bỏ kiểm tra owner để ép `ok:true`.
- Nếu hai signal cùng active: thu thêm capture ở chức năng khác cũng mở Select file, hoặc hook receiver/handler ứng viên để phân biệt. Backtrace chứa return addresses, không tự là địa chỉ đầu hàm có thể gọi.
- Giữ nguyên việc phân biệt queued/started/outcome/completed và generation.
- Không phục hồi `-355`, không đọc lại `item+0x20`, không dùng pointer không-null làm bằng chứng live, không dùng timing/fingerprint ordinal để ép chọn candidate.
- Khi đã verified trên test, mới kiểm tra thao tác nhập path/OK và output ở giai đoạn kế tiếp. Build hiện tại cố ý chặn `y/z/e/v/p/w`; RPC legacy Save trả lỗi `LEGACY_SAVE_DISABLED_USE_H_J_M`.

## Giới hạn cần hiểu đúng

- Chưa có cơ chế tự chứng minh report query hoàn tất; người vận hành xác nhận trước h.
- Kích hoạt QSignal trực tiếp có thể bỏ qua trạng thái enabled của menu. Chưa có readback enabled theo DLL thực tế; chỉ thử lúc report sẵn sàng như lượt bấm tay đã học.
- Caption/exec/form là bằng chứng trong Qt, không phải xác minh pixel hay file đã xuất thành công.
- Đường xử lý async có thể không còn QSignal active khi dialog được tạo; trường hợp đó phải discovery handler khác, không lấy signal gần nhất theo thời gian.
- Ngay cả khi replay hoạt động trên desktop mở, chưa chứng minh chạy khi lock screen/RDP disconnect/Session 0. Phải kiểm thử riêng.
- Bản runner mặc định giữ cách spawn không truyền cwd của luồng cũ. Muốn thử riêng working directory, dùng `python flow_test.py --cwd-exe` hoặc thêm `ITC_WORKDIR` vào config. Ghi baseline trước, không đồng thời đổi DLL/config/cwd.
- `q` giữ app mở sau khi dispose/detach. Vì luồng Connect cũ có CModule timer native, runner đếm timer/callback, kiểm tra idle và chờ thêm acknowledgement ở một lần dispatch trên GUI thread trước khi unload. `WAITING_GUI_DISPOSE_ACK` có thể cần một GUI event bình thường nếu wake không đi qua dispatcher. Cancel/đóng các dialog đang chờ hoặc tương tác bình thường với ITC rồi q lại. Khi shutdown đã bắt đầu, không chạy tiếp lệnh automation mới. Nếu target crash/đóng thì runner ghi log và thoát. Đừng force-unload script khi callback native còn dùng code của nó.

## Kiểm tra đã chạy ở môi trường phát triển

- JavaScript syntax, Python AST, CLI help; không còn literal `-355`, `0x20` hoặc `destroyed_flag_ignored` trong agent runtime.
- 8 kịch bản Frida JS mock: học/replay hợp lệ; hai signal ambiguous; sai owner; hủy/tái dùng địa chỉ; disconnect; wake thất bại; native return không có outcome; thiếu lifecycle hook. Kiểm tra còn bảo đảm không truyền integer cho activate và giữ verified sau các lần đọc report.
- 4 test runner với Frida mock: luồng h/j/m và log local; cwd explicit; q bị từ chối khi modal rồi retry; lỗi setup cleanup đúng PID suspended do runner tạo.
- Bootstrap mock: RPC cũ cần thiết còn tồn tại, startup đợi Qt, x64 bị chặn, legacy Save bị vô hiệu hóa.
- Các test này không chứng minh ABI hoặc hành vi modal của Qt3 native. Cần chạy quy trình trên test và dựa vào log thật để kết luận.
