# Handoff cho Kiro — rebuild Qt3 native minimal từ source

Ngày: 2026-11-03, Asia/Saigon. Bản implementation: 0.2.

## Mục đích và ranh giới

Người dùng muốn review và build nội bộ một công cụ automation cho app Qt3 Windows x86. ZIP trước đó bị trống/xóa khi tải vào máy công ty; nguyên nhân chưa được xác minh. File này là source code minh bạch để kiểm tra và dựng lại trong môi trường được phép. Markdown không chứng minh công cụ được công ty cho phép và không bảo đảm không bị chặn.

Kiro: dùng quy trình review/build/phân phối nội bộ đã được phê duyệt. Không tắt hay thay đổi EDR/AV, không đổi tên/ngụy trang artifact để tránh phát hiện, không thử các kênh khác để vượt chặn. Nếu dependency hoặc binary build bị chặn, giữ log và xử lý qua IT/security. File không chứa DLL/EXE, base64, binary payload hay script giải mã binary.

Người dùng đã xác nhận Frida PoC hiện có được phê duyệt. Điều đó không tự chứng minh mọi DLL mới/target/profile đều được chấp thuận. Không tự attach, spawn hoặc thử thao tác với app thật chỉ vì đọc handoff này; operator chọn PID và thực hiện theo phạm vi được phê duyệt. Không thu thập/gửi dữ liệu khách hàng, credential hoặc binary proprietary.

## Bản này làm gì

Python SDK → Frida loader/C ABI → DLL native Qt3 → Qt GUI thread → QObject/QWidget.

Frida chỉ inventory, nạp/khởi động DLL và chuyển request qua C ABI. QObject tree, guarded lifetime IDs, stale-element rejection và widget actions nằm trong C++. Đây là implementation mới của backend/widget layer và protocol concepts của QtWebDriver; chưa phải toàn bộ Cisco QtWebDriver được port.

Đã có: window, button, QLineEdit Unicode, menu/submenu, checkbox hai trạng thái, Qt3 QFileDialog; lazy locator; strict ambiguity; bounded wait; timeout-before-dispatch cancellation; outcome-unknown ticket và reconcile; JSONL có che nội dung.

Chưa có: native Win32 common file dialog, arbitrary custom widgets, QTextEdit, tri-state checkbox; chưa xác minh app thật, locked session, độ bền nhiều giờ, hoặc độ ổn định hơn Frida agent cũ.

## Điều quan trọng nhất: ABI

Source native và recipe ở đây được kiểm chứng với QtWin p8 (Qt 3.3.8) + MinGW GCC 3.4.5 x86. DLL tên qt-mt.dll hoặc cùng version không chứng minh ABI tương thích. App thật có thể dùng MSVC/Qt build khác.

1. Có thể tạo controller/loader và chạy `--probe-only` trước khi có SDK, backend DLL hoặc profile. Chế độ này có Frida agent trong process nhưng không nạp backend, không gọi QObject API và không điều khiển UI.
2. Thu fingerprint của app thật trước; xem kiến trúc, Qt hash, exports/imports/version và các native window classes.
3. Nếu app thật dùng SDK/compiler khác, phải có SDK/headers/import library/compiler/build options tương ứng và xác minh riêng. Recipe MinGW lab này không tự port sang MSVC. `qt_get_application_thread_id()` là scalar export riêng của build Qt đã pin; profile khác cần phương án thread bootstrap được kiểm chứng.
4. Không chỉnh hash profile để ép nạp. `profiles/lab.json` phải được sinh từ build thực tế và chỉ được dùng với Qt/runtime tương ứng. Rebuild có thể thay hash vì PE timestamp; không giữ hash DLL cũ cho DLL mới.
5. Không chép Qt DLL lab hoặc MinGW runtime vào thư mục app thật, không thay dependency của app thật để làm nó khớp.

## Việc Kiro cần làm

- Review source trước. Tạo các file theo từng heading `FILE: relative/path` ở phần dưới, UTF-8, xuống dòng LF. Không sửa source để bỏ kiểm tra profile, GUI thread, ambiguity, stale hoặc che log.
- Xác minh nội dung file theo bảng SHA-256 (hash của UTF-8/LF, không bao gồm code fences).
- Chuẩn bị Python 3.10+ và Frida được phê duyệt. Version đã test: Frida 17.25.1, Python 3.14 x64 điều khiển target Windows x86. Không có Frida binary trong handoff.
- Chạy probe trước với PID do operator chọn. Chưa cần C++ toolchain cho bước này.
- Nếu chỉ cần tái tạo lab: dùng SDK/toolchain đã được phê duyệt hoặc recipe lab tùy chọn bên dưới, mặc định lấy từ cache offline có kiểm SHA-256.
- Build backend và fixture riêng bằng `scripts/build_backend.py`. Script này không download, không nạp DLL vào app và không chạy workflow.
- Chạy `scripts/smoke_lab.py` chỉ trên fixture do nó tự tạo. Không chuyển smoke test sang PID app thật.
- Ghi riêng kết quả mới của máy công ty; không coi kết quả test cũ là test đã chạy tại đó.

## Cấu trúc file

```text
qt3-native-minimal/
  requirements.txt
  LICENSE
  python/qt3wd.py
  python/summarize.py
  agent/loader.js
  native/backend.cpp
  native/backend.h
  native/backend.pro
  scripts/build_backend.py
  scripts/build_lab_sdk.py       # tùy chọn: chỉ dựng SDK lab
  scripts/smoke_lab.py           # tùy chọn: chỉ thử fixture riêng
  lab/fixture.cpp               # tùy chọn, không phát hành trong minimal
  lab/fixture.h
  lab/fixture.pro
  runtime/qt3webdriver.dll      # sinh sau build, không có trong handoff
  profiles/lab.json             # sinh sau build, không có hash giả định
```

## Lệnh chạy theo từng giai đoạn

Chạy từ root dự án vừa tạo; đường dẫn build/cache bên dưới là ví dụ, chọn thư mục được công ty cho phép.

### A. Dependency và probe

Nếu dependency/version đã được chấp thuận:

```powershell
python -m pip install -r requirements.txt
python python/qt3wd.py --pid 1234 --probe-only --logs logs/probe-01
```

Thay 1234 bằng PID operator chọn. Kết quả cần xem/gửi lại sau review: `fingerprint.json` và `trace.jsonl` trong thư mục log. Chưa cần native DLL/profile cho probe.

Không tự đổi attach sang spawn sau lỗi. Nếu operator chủ động chọn spawn và môi trường cho phép, controller có `--spawn`, `--app-arg` và `--cwd`. Không retry bằng cách thay đổi security controls.

### B. Có SDK Qt3 MinGW phù hợp sẵn

```powershell
python scripts/build_backend.py --sdk C:/Approved/Qt3 --compiler C:/Approved/MinGW --work-dir work/native-build --with-fixture
python scripts/smoke_lab.py
```

`--with-fixture` tạo app tự kiểm thử và đặt Qt/runtime chỉ trong `lab-runtime/`. Minimal field kit chỉ cần DLL backend, controller, agent, profile, requirements và notices/source; không cần thư mục lab-runtime.

### C. Tùy chọn dựng lại SDK lab từ các artifact được phê duyệt

`scripts/build_lab_sdk.py` ghi rõ URL và SHA-256 của từng dependency. Mặc định KHÔNG download. Đặt đúng artifact từ kênh được phê duyệt vào cache, rồi chạy:

```powershell
python scripts/build_lab_sdk.py --work-dir work/qt3-sdk --cache C:/Approved/Qt3Cache --drive Q
python scripts/build_backend.py --sdk work/qt3-sdk/deps/qt-3.3.x-p8 --compiler work/qt3-sdk/deps/mingw345 --work-dir work/native-build --with-fixture
python scripts/smoke_lab.py
```

Chọn drive letter chưa dùng. Recipe tạo alias tạm tới thư mục work và gỡ alias trong finally; không thay PATH hệ thống. Khi resume dùng cùng drive letter và `--resume`. Compiler/7-Zip chỉ được giải nén cục bộ, không chạy installer. Chỉ dùng `--allow-download` nếu việc lấy các dependency đó đã được cho phép; hash mismatch phải dừng, không bỏ kiểm tra. Nếu policy chặn, dừng và làm việc với IT/security.

Recipe đã biết: MinGW 3.4.2 C++ driver/linker lỗi trên máy dev ban đầu; overlaid cả GCC core và C++ 3.4.5 matching packages mới qua compiler smoke test. Qt source cần hai sửa đổi build-file: VERSION rỗng để linker tạo qt-mt.dll thật (không rename DLL), và bỏ QSound header khỏi moc khi sound đã tắt. Build helper giữ nguyên các thay đổi này.

### D. Kiểm thử fixture và inspection sau khi profile hợp lệ

`smoke_lab.py` tự mở/dừng app fixture riêng; kiểm tra GUI thread, window, input, button, checkbox idempotence, menu/submenu, stale handle và Qt3 file dialog. Không nhận production PID.

Sau review và có profile đúng cho một target được phép:

```powershell
python python/qt3wd.py --pid 1234 --logs logs/inspect-01 --show-names
```

CLI inspection không tự click/fill. Khi viết workflow SDK, tạo `Driver(..., actions=True)` một cách chủ động; một backend giữ mode từ lần init đầu, nên restart app thử nghiệm trước khi đổi mode hoặc thay DLL. Controller detach không FreeLibrary: DLL/Qt dispatcher còn trong app đến khi app kết thúc bình thường.

Native init xác minh cả thread sở hữu HWND và Qt application thread đã được build này ghi nhận. Tất cả QObject/guard/widget operations nằm trên GUI thread. Frida không parse container layout hoặc gọi Qt C++ member bằng offset/ABI đoán.

## Cách dùng SDK và log

`driver.locator(name=..., class_name=..., caption=..., text=..., scope=...)` resolve lại mỗi lần thao tác; kết quả phải duy nhất. Handle explicit giữ nguyên một lifetime; object bị hủy phải báo stale, kể cả địa chỉ được tái sử dụng. Menu dùng đường dẫn text, resolve lại sau aboutToShow; không giữ item pointer/index qua workflow.

Các action: `activate()`, `click()`, `fill(text)`, `check(bool)`, `menu(*segments)`, `file_path(path)`, `accept_file()`, `cancel_dialog()`. `describe()`, `snapshot()` và `drain_events()` dùng để đọc trạng thái/log. Đọc `python/qt3wd.py` bên dưới để xem API đầy đủ.

Action mở dialog bằng exec() có thể chờ đến khi dialog đóng. Dùng thread/future cho lệnh mở và request khác để thao tác dialog; dispatcher hỗ trợ nested loop. File accept chỉ xác nhận dispatch, vẫn phải kiểm tra dialog đóng và kết quả mong muốn.

`outcome unknown` không phải lệnh chưa chạy. Giữ ticket, gọi `reconcile(ticket)` và xác minh postcondition; không tự bấm lại. `Trace.scenario(...)` ghi kết quả workflow, `summarize.py` tách chúng khỏi lỗi native. Missing tạm thời khi chờ và stale chủ động trong test không đồng nghĩa workflow thất bại.

Log mặc định che text/name/caption/path/arguments; opaque element ID, thread ID, correlation/ticket và timing vẫn giúp đối chiếu. Password không trả text ngay cả khi include-content. Không gửi log có nội dung nhạy cảm; không bật include-content cho log cần chia sẻ. Lifecycle ring có 512 sự kiện giữa hai lần drain và báo dropped; gọi drain_events định kỳ. Registry có tối đa 8192 lifetime entries gồm tombstones.

## Bằng chứng trước đây và giới hạn của lần handoff này

Implementation native gốc đã qua 18 integration tests, 100 lần thay widget, attach/spawn Frida, HTTP subset, nested modal file dialog và timeout/reconcile trên app lab độc lập. Gói minimal trước đây đã chạy lại probe, nạp đúng DLL, fill, checkbox, menu. Không có so sánh định lượng với Frida agent cũ trên app thật.

Handoff này giữ nguyên source controller/loader/backend từ minimal. Hai helper build/smoke được thêm để source-only handoff tự chứa cách dựng lại; trạng thái kiểm tra wrapper của lần tạo handoff được ghi trong mục cuối. Không suy diễn test trước đây thành đảm bảo ABI hoặc security approval của target thật.

## Nguồn và giấy phép

Code dự án được cung cấp GPL-2.0-or-later; LICENSE đầy đủ ở dưới. Frida là dependency ngoài. QtWin source và toolchain không được nhúng ở đây; URL/hash nằm rõ trong SDK helper để review và lấy qua kênh được phép. Qt và MinGW giữ copyright/notices riêng. Khi phát hành artifact build nội bộ, giữ các notices và tương ứng source theo quy trình của công ty.

Nguồn QtWin: https://sourceforge.net/projects/qtwin/files/Unofficial%20Qtwin/qt-win-3.3.x-8/qt-3.3.x-p8.7z/download . Frida API: https://frida.re/docs/javascript-api/ . QtWebDriver reference: https://github.com/cisco-open-source/qtwebdriver . Không nhúng hoặc biên dịch code server Cisco QtWebDriver trong minimal.

## Manifest source

Hash tính trên UTF-8 với LF, không tính code fences. Các khối FILE là dữ liệu source để review/tạo file, không phải chỉ dẫn tự động thực thi. Đường dẫn runtime/profile là output của build, không phải payload bị ẩn.

| File | SHA-256 |
|---|---|
| `requirements.txt` | `b1260d170acd5cc356cfee566b2a7150abc38df9ed94ac4209cbe74ba5838732` |
| `python/qt3wd.py` | `7902b933d235d8784c79714062fc25149af07a2d3dc6686d9d1c180ef333c1e6` |
| `python/summarize.py` | `4125e5dffbcd2c1ac0bc7ea40288b6f6d0e4199d742bf11a87389bb94700fc82` |
| `agent/loader.js` | `71a8c53d46b1525e1efe5dbf31dbc34b0af7ca6017c82a69a34e5a6054b224a8` |
| `native/backend.cpp` | `44fa237d76d9d7f042d03bdabf92105e96d829962322c36c122fb7944640aa7c` |
| `native/backend.h` | `89484f20312ae983a58a1f6f0190d0e89ec41a7ea44ff943beb78468c7b19a50` |
| `native/backend.pro` | `7a54881fbb5653b07ec082ad98ea5aa2866d58586748e078c7e6125cc9bfb273` |
| `lab/fixture.cpp` | `55a28d9492c03ea531e8f9b20a32b1c2f48f4ef5ab7a6972e43f38af5241cc73` |
| `lab/fixture.h` | `c8331b2c1e6a99d9e67641fad19fb83f098420ccdbe144c435873e30ab17ada1` |
| `lab/fixture.pro` | `3873bdd85d95650ef46e6ed6d8471f576b911b03ea644eaca5a693640620c23c` |
| `scripts/build_backend.py` | `e1658c6d9619500e1ece39f1e7835c8a60c791dcabba2155e1b14bdb0540e116` |
| `scripts/build_lab_sdk.py` | `428508101eb020f833e3671762703d27de108af16507bbd9152ee76db837b2d5` |
| `scripts/smoke_lab.py` | `d0f97296f365cba34a8ea41facf32d9488fce8c536c25349221e5994cb05bf31` |
| `LICENSE` | `32b1062f7da84967e7019d01ab805935caa7ab7321a7ced0e30ebe75e5df1670` |

## FILE: requirements.txt

```text
# Yeu cau Python >= 3.10 tren Windows.
# Cai dat: python -m pip install -r requirements.txt
# Phien ban da kiem thu voi backend Qt3 native.
# Cac module Python con lai thuoc thu vien chuan.
frida==17.25.1
```

## FILE: python/qt3wd.py

```python
"""Experimental Qt3 native backend client and evidence collector."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import quote
import uuid

ROOT=Path(__file__).resolve().parents[1]
SENSITIVE={'text','name','caption','path','selectedFile','input','selector','arguments','message','errorMessage','description'}


class BackendError(Exception):
    def __init__(self,code,message,ticket=None):
        self.code,self.ticket=code,ticket
        super().__init__(f'{code}: {message}')


class Trace:
    def __init__(self,directory,include_content=False):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.run_id=uuid.uuid4().hex;self.salt=secrets.token_bytes(32)
        self.include_content=include_content;self.lock=threading.Lock();self.sequence=0
    def redact(self,value,key=''):
        if key in SENSITIVE and not self.include_content and value is not None:
            raw=json.dumps(value,ensure_ascii=False,sort_keys=True).encode()
            return {'redacted':True,'bytes':len(raw),'runHash':hashlib.sha256(self.salt+raw).hexdigest()}
        if isinstance(value,dict):return {k:self.redact(v,k) for k,v in value.items()}
        if isinstance(value,(list,tuple)):return [self.redact(v) for v in value]
        return value
    def event(self,event,**fields):
        with self.lock:
            self.sequence+=1
            row={'schema':1,'runId':self.run_id,'sequence':self.sequence,'monotonicNs':time.monotonic_ns(),
                 'wallUtc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'event':event,**self.redact(fields)}
            with (self.directory/'trace.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    def save(self,name,value):
        (self.directory/name).write_text(json.dumps(self.redact(value),indent=2,ensure_ascii=False),encoding='utf-8')
    @contextmanager
    def scenario(self,label):
        scenario=uuid.uuid4().hex;started=time.monotonic()
        self.event('scenario_start',scenarioId=scenario,scenario=label)
        try:
            yield
        except Exception as error:
            self.event('scenario_end',scenarioId=scenario,scenario=label,passed=False,
                       durationMs=(time.monotonic()-started)*1000,errorMessage=str(error))
            raise
        else:self.event('scenario_end',scenarioId=scenario,scenario=label,passed=True,durationMs=(time.monotonic()-started)*1000)


def window_for_pid(pid,timeout=10):
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowThreadProcessId.restype=wintypes.DWORD
    user.IsWindowVisible.argtypes=[wintypes.HWND];user.IsWindowVisible.restype=wintypes.BOOL
    user.GetWindow.argtypes=[wintypes.HWND,wintypes.UINT];user.GetWindow.restype=wintypes.HWND
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    found=[]
    @callback_type
    def callback(hwnd,_):
        owner=wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value==pid and user.IsWindowVisible(hwnd) and not user.GetWindow(hwnd,4):found.append(int(hwnd))
        return True
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        found.clear();user.EnumWindows(callback,0)
        if found:return found[0]
        time.sleep(.05)
    raise BackendError('gui unavailable','No visible top-level target window; specify --hwnd if needed')


def file_hash(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda:file.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def native_window_classes(pid):
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowThreadProcessId.restype=wintypes.DWORD
    user.GetClassNameW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user.IsWindowVisible.argtypes=[wintypes.HWND]
    rows=[]
    @ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def visit(hwnd,_):
        owner=wintypes.DWORD();thread=user.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value==pid:
            buffer=ctypes.create_unicode_buffer(256);user.GetClassNameW(hwnd,buffer,256)
            rows.append({'windowClass':buffer.value,'guiThread':thread,'visible':bool(user.IsWindowVisible(hwnd))})
        return True
    user.EnumWindows(visit,0)
    return rows


def validate_profile(inventory,profile,backend):
    if inventory['arch']!='ia32' or inventory['pointerSize']!=4:
        raise BackendError('abi unsupported','This build requires Windows x86')
    if len(inventory['qt'])!=1 or inventory['qt'][0]['name'].lower()!='qt-mt.dll':
        raise BackendError('abi unsupported','Expected exactly one loaded qt-mt.dll')
    if file_hash(inventory['qt'][0]['path'])!=profile['qt_sha256']:
        raise BackendError('abi unsupported','Qt DLL hash does not match the tested native profile; collect fingerprint and build a matching backend')
    if file_hash(backend)!=profile['artifacts']['qt3webdriver.dll']:
        raise BackendError('artifact mismatch','Backend hash does not match the build profile')
    runtimes=[m for m in inventory['modules'] if m['name'].lower()=='mingwm10.dll']
    if len(runtimes)!=1 or file_hash(runtimes[0]['path'])!=profile['artifacts']['mingwm10.dll']:
        raise BackendError('abi unsupported','Loaded MinGW thread runtime does not match the tested profile')
    return True


class Driver:
    def __init__(self,trace,*,pid=None,spawn=None,spawn_args=None,cwd=None,actions=False,profile=None,hwnd=None,probe_only=False):
        import frida
        self.trace=trace;self.device=frida.get_local_device();self.session=None;self.script=None
        self.identity=uuid.uuid4().hex;self.pending=set();self.actions=actions;self.backend_ready=False
        self.pid=pid;self.spawned=False
        trace.event('controller_start',fridaVersion=frida.__version__,actions=actions,probeOnly=probe_only,
                    packageVersion='0.2',controllerSha256=file_hash(Path(__file__)),agentSha256=file_hash(ROOT/'agent'/'loader.js'))
        try:
            if spawn:
                executable=Path(spawn).resolve()
                self.pid=self.device.spawn([str(executable),*(spawn_args or [])],cwd=str(Path(cwd).resolve() if cwd else executable.parent),stdio='pipe');self.spawned=True
                trace.event('process_spawned',pid=self.pid,path=str(executable),arguments=spawn_args or [])
            if not self.pid:raise BackendError('invalid argument','Supply a PID or executable')
            self.session=self.device.attach(self.pid)
            self.session.on('detached',lambda reason,crash:trace.event('session_detached',reason=str(reason),crashPresent=crash is not None))
            self.script=self.session.create_script((ROOT/'agent'/'loader.js').read_text(encoding='utf-8'))
            self.script.on('message',self._message);self.script.load()
            if self.spawned:self.device.resume(self.pid);self.spawned=False
            self.inventory=self.script.exports_sync.inventory()
            self._fingerprint()
            if probe_only:return
            metadata=json.loads(Path(profile or ROOT/'profiles'/'lab.json').read_text(encoding='utf-8'))
            backend=ROOT/'runtime'/'qt3webdriver.dll'
            validate_profile(self.inventory,metadata,backend)
            trace.event('profile_matched',profile=metadata['profile'],qtHash=metadata['qt_sha256'],
                        backendHash=metadata['artifacts']['qt3webdriver.dll'])
            target_hwnd=int(hwnd,0) if isinstance(hwnd,str) else hwnd or window_for_pid(self.pid)
            armed=self.script.exports_sync.begin(str(backend.resolve()),hex(target_hwnd),actions)
            trace.event('bootstrap_armed',details=armed)
            deadline=time.monotonic()+10
            while True:
                state=self.script.exports_sync.status()
                if state['state']=='ready':break
                if state['state']=='failed':raise BackendError('bootstrap failed',str(state))
                if time.monotonic()>deadline:raise BackendError('bootstrap timeout','GUI thread did not initialize backend')
                time.sleep(.02)
            self.backend_ready=True
            info=self.call('INFO')
            if bool(info['actionsEnabled'])!=bool(actions):
                raise BackendError('mode mismatch','An existing backend has another mode; restart the app before changing mode')
            trace.save('backend-info.json',info)
        except Exception as error:
            trace.event('connection_failed',errorType=type(error).__name__,errorMessage=str(error))
            self.close();raise

    def _message(self,message,data):
        if message.get('type')=='send':self.trace.event('agent',payload=message.get('payload'))
        else:self.trace.event('agent_error',description=message.get('description'),line=message.get('lineNumber'))

    def _fingerprint(self):
        record={'pid':self.inventory['pid'],'arch':self.inventory['arch'],'pointerSize':self.inventory['pointerSize'],
                'nativeWindows':native_window_classes(self.pid),'qt':[]}
        for module in self.inventory['qt']:
            item={**module,'sha256':file_hash(module['path'])}
            record['qt'].append(item)
        self.trace.save('fingerprint.json',record)
        self.trace.event('fingerprint',arch=record['arch'],qtModules=len(record['qt']),
                         qtHashes=[m['sha256'] for m in record['qt']])

    def call(self,command,*arguments,timeout=5):
        request='\t'.join(quote(str(x),safe='') for x in (command,*arguments))
        if len(request.encode())>=8192:raise BackendError('invalid argument','Request exceeds native limit')
        correlation=uuid.uuid4().hex
        element_commands={'DESCRIBE','CLICK','FILL','CHECK','WINDOW','MENU','MENU_ITEMS','FILE_PATH','FILE_ACCEPT','DIALOG_CANCEL'}
        self.trace.event('request',correlation=correlation,command=command,arguments=arguments,deadlineMs=round(timeout*1000),
                         elementId=arguments[0] if command in element_commands and arguments else None,
                         scopeId=arguments[0] if command=='FIND' and arguments else None,
                         input=arguments[1] if command=='FILL' and len(arguments)>1 else None)
        try:ticket=self.script.exports_sync.submit(request)
        except Exception as error:
            self.trace.event('transport_exception',correlation=correlation,phase='submit',errorMessage=str(error))
            raise BackendError('outcome unknown','Transport failed during submit; do not replay the action') from error
        if not ticket:raise BackendError('queue unavailable','Backend not ready or queue full')
        self.trace.event('queued',correlation=correlation,ticket=ticket)
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:reply=self.script.exports_sync.poll(ticket)
            except Exception as error:
                self.pending.add(ticket)
                self.trace.event('transport_exception',correlation=correlation,ticket=ticket,phase='poll',errorMessage=str(error))
                raise BackendError('outcome unknown','Transport failed after queuing; reconcile if the target is still available',ticket) from error
            if reply['state']==1:
                return self._result(reply['reply'],correlation)
            if reply['state']<0:raise BackendError('transport error','Native ticket is unavailable',ticket)
            time.sleep(min(.01,max(0,deadline-time.monotonic())))
        cancelled=self.script.exports_sync.cancel(ticket)
        if cancelled==1:
            self.trace.event('cancelled_before_dispatch',correlation=correlation,ticket=ticket)
            raise BackendError('timeout before dispatch','Queued request was cancelled without execution',ticket)
        self.pending.add(ticket)
        self.trace.event('outcome_unknown',correlation=correlation,ticket=ticket,command=command)
        raise BackendError('outcome unknown','Request may have executed; use reconcile(ticket) and check postconditions',ticket)

    def _result(self,envelope,correlation=None):
        self.trace.event('reply',correlation=correlation,envelope=envelope)
        result=envelope['result']
        if 'error' in result:raise BackendError(result['error'],result['message'])
        return result['value']

    def reconcile(self,ticket):
        reply=self.script.exports_sync.poll(ticket)
        self.trace.event('reconcile',ticket=ticket,state=reply['state'])
        if reply['state']!=1:return None
        self.pending.discard(ticket)
        return self._result(reply['reply'])

    def locator(self,*,name='',class_name='',scope=None,text='',caption=''):return Locator(self,name,class_name,scope,text,caption)
    def handle(self,id):return Handle(self,id)
    def snapshot(self):return self.call('TREE')
    def drain_events(self):
        result=self.call('EVENTS')
        self.trace.event('native_lifecycle',details=result)
        return result
    def close(self):
        if self.backend_ready and self.session:
            try:self.drain_events()
            except Exception as error:self.trace.event('lifecycle_drain_failed',errorMessage=str(error))
            self.backend_ready=False
        if self.spawned and self.pid:
            try:self.device.resume(self.pid)
            except Exception:pass
            self.spawned=False
        if self.script:
            try:self.script.exports_sync.disarm()
            except Exception:pass
        if self.session:
            try:self.session.detach()
            except Exception:pass
            self.session=None
        self.trace.event('controller_closed',pid=self.pid,pendingTickets=list(self.pending),targetLeftRunning=True)


class Handle:
    def __init__(self,driver,id):self.driver,self.id,self.session=driver,id,driver.identity
    def _call(self,command,*args,timeout=5):
        if self.session!=self.driver.identity:raise BackendError('invalid session','Handle belongs to another session')
        return self.driver.call(command,self.id,*args,timeout=timeout)
    def describe(self):return self._call('DESCRIBE')
    def click(self,timeout=5):return self._call('CLICK',timeout=timeout)
    def fill(self,text):return self._call('FILL',text)
    def check(self,checked=True):return self._call('CHECK','true' if checked else 'false')
    def activate(self):return self._call('WINDOW')
    def menu(self,*segments,timeout=10):return self._call('MENU',*segments,timeout=timeout)
    def menu_items(self):return self._call('MENU_ITEMS')
    def file_path(self,path):return self._call('FILE_PATH',str(path))
    def accept_file(self):return self._call('FILE_ACCEPT')
    def cancel_dialog(self):return self._call('DIALOG_CANCEL')


class Locator:
    def __init__(self,driver,name,cls,scope,text='',caption=''):
        self.driver,self.name,self.cls,self.scope=driver,name,cls,scope
        self.text,self.caption=text,caption
    def resolve(self,timeout=3):
        deadline=time.monotonic()+timeout
        while True:
            if time.monotonic()>=deadline:raise BackendError('locator timeout','No matching widget before deadline')
            scope=self.scope.resolve(max(.001,deadline-time.monotonic())).id if isinstance(self.scope,Locator) else (self.scope.id if self.scope else '')
            if time.monotonic()>=deadline:raise BackendError('locator timeout','Scope resolution exhausted the deadline')
            try:return Handle(self.driver,self.driver.call('FIND',scope,self.cls,self.name,self.text,self.caption,timeout=max(.001,deadline-time.monotonic())))
            except BackendError as error:
                if error.code=='timeout before dispatch':raise BackendError('locator timeout','No matching widget before deadline') from error
                if error.code!='no such element':raise
                if time.monotonic()>=deadline:raise BackendError('locator timeout','No matching widget before deadline') from error
                time.sleep(min(.02,max(0,deadline-time.monotonic())))
    def describe(self):return self.resolve().describe()
    def click(self,timeout=5):return self.resolve().click(timeout)
    def fill(self,text):return self.resolve().fill(text)
    def check(self,value=True):return self.resolve().check(value)
    def activate(self):return self.resolve().activate()
    def menu(self,*segments,timeout=10):return self.resolve().menu(*segments,timeout=timeout)
    def file_path(self,path):return self.resolve().file_path(path)
    def accept_file(self):return self.resolve().accept_file()
    def cancel_dialog(self):return self.resolve().cancel_dialog()
    def wait(self,predicate,timeout=3):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                value=self.resolve(max(.001,deadline-time.monotonic())).describe()
                if predicate(value):return value
            except BackendError as error:
                if error.code not in {'no such element','stale element reference','locator timeout'}:raise
            time.sleep(min(.02,max(0,deadline-time.monotonic())))
        raise BackendError('postcondition timeout','Condition did not become true')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--pid',type=int);group.add_argument('--spawn',type=Path)
    parser.add_argument('--probe-only',action='store_true')
    parser.add_argument('--enable-actions',action='store_true')
    parser.add_argument('--include-content',action='store_true')
    parser.add_argument('--show-names',action='store_true',help='Print object names locally; saved logs remain redacted unless include-content is set')
    parser.add_argument('--app-arg',action='append',default=[])
    parser.add_argument('--cwd',type=Path)
    parser.add_argument('--hwnd')
    parser.add_argument('--logs',type=Path,default=Path('logs')/time.strftime('qt3wd-%Y%m%d-%H%M%S'))
    parser.add_argument('--profile',type=Path)
    args=parser.parse_args();trace=Trace(args.logs,args.include_content);driver=None
    try:
        driver=Driver(trace,pid=args.pid,spawn=args.spawn,spawn_args=args.app_arg,cwd=args.cwd,actions=args.enable_actions,hwnd=args.hwnd,
                      profile=args.profile,probe_only=args.probe_only)
        if args.probe_only:print('Fingerprint collected; backend was not loaded.')
        else:
            tree=driver.snapshot();trace.save('tree.json',tree)
            print(f'Connected. Snapshot: {len(tree["objects"])} objects. Actions enabled: {args.enable_actions}.')
            if args.show_names:print(json.dumps(tree,ensure_ascii=True,indent=2))
            print('Use the Python Driver API for explicit actions; CLI inspection performs none.')
        print(f'Logs: {args.logs.resolve()}')
    except Exception as error:
        trace.event('run_failed',errorType=type(error).__name__,errorMessage=str(error))
        print(f'Run stopped: {error}. Logs: {args.logs.resolve()}')
        raise SystemExit(1)
    finally:
        if driver:driver.close()


if __name__=='__main__':main()
```

## FILE: python/summarize.py

```python
"""Summarize traces without treating expected stale-handle probes as workflow failures."""
import argparse
from collections import Counter
import json
from pathlib import Path


def percentile(values,fraction):
    if not values:return None
    values=sorted(values);return values[min(len(values)-1,round((len(values)-1)*fraction))]


def summarize(directory):
    commands=Counter();errors=Counter();events=Counter();queue=[];execution=[];scenarios=[];malformed=0;dropped=0
    for file in sorted(Path(directory).rglob('trace*.jsonl')):
        with file.open(encoding='utf-8') as source:
            for line in source:
                try:row=json.loads(line)
                except ValueError:malformed+=1;continue
                event=row.get('event');events[event]+=1
                if event=='request':commands[row.get('command','unknown')]+=1
                if event=='reply':
                    native=row.get('envelope',{});queue.append(native.get('queueMs',0));execution.append(native.get('executeMs',0))
                    result=native.get('result',{})
                    if 'error' in result:errors[result['error']]+=1
                if event=='scenario_end':scenarios.append(row)
                if event=='native_lifecycle':dropped+=row.get('details',{}).get('dropped',0)
    return {'commands':dict(commands),'nativeErrorCounts':dict(errors),'events':dict(events),
            'queueMs':{'p50':percentile(queue,.5),'p95':percentile(queue,.95),'max':max(queue) if queue else None},
            'executeMs':{'p50':percentile(execution,.5),'p95':percentile(execution,.95),'max':max(execution) if execution else None},
            'scenarios':{'completed':len(scenarios),'passed':sum(r.get('passed') is True for r in scenarios),
                         'failed':sum(r.get('passed') is False for r in scenarios)},
            'lifecycleEventsDropped':dropped,'malformedLines':malformed,
            'interpretation':'Native errors include transient missing elements during waits and intentional stale/missing tests. Only explicit scenario_end records measure workflow outcomes.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('logs',type=Path);p.add_argument('--out',type=Path)
    a=p.parse_args();result=summarize(a.logs);encoded=json.dumps(result,indent=2,ensure_ascii=False)
    if a.out:a.out.write_text(encoded,encoding='utf-8')
    print(encoded)
```

## FILE: agent/loader.js

```javascript
'use strict';
// Frida only inventories modules, loads the matched backend, and bootstraps it
// on an observed Windows GUI thread. All QObject access lives in the DLL.
let backend=null, api=null, boot={state:'not-started'}, hooks=[];
function inventory() {
  const modules=Process.enumerateModules();
  const qt=modules.filter(m => /^qt-mt[^\\/]*\.dll$/i.test(m.name));
  return {pid:Process.id,arch:Process.arch,pointerSize:Process.pointerSize,
    modules:modules.map(m=>({name:m.name,path:m.path,size:m.size})),
    qt:qt.map(m=>({name:m.name,path:m.path,size:m.size,version:m.version||null,
      importedModules:[...new Set(m.enumerateImports().map(e=>e.module).filter(Boolean))].sort(),
      exports:m.enumerateExports().map(e=>({name:e.name,type:e.type}))}))};
}
function begin(path, hwndText, actions) {
  if(boot.state!=='not-started')throw new Error('Bootstrap has already been attempted');
  if(Process.platform!=='windows'||Process.arch!=='ia32')throw new Error('Backend requires Windows x86');
  const hwnd=ptr(hwndText), user=Process.getModuleByName('user32.dll');
  const getThread=new NativeFunction(user.getExportByName('GetWindowThreadProcessId'),'uint',['pointer','pointer'],'stdcall');
  const pidOut=Memory.alloc(4),tid=getThread(hwnd,pidOut);
  if(!tid||pidOut.readU32()!==Process.id)throw new Error('Window does not belong to target');
  backend=Module.load(path);
  const fn=(name,result,args)=>new NativeFunction(backend.getExportByName(name),result,args,'mscdecl');
  api={prepare:fn('qt3wd_prepare','int',[]),start:fn('qt3wd_start','int',['ulong','int']),
    submit:fn('qt3wd_submit','ulong',['pointer']),poll:fn('qt3wd_poll','int',['ulong','pointer','ulong']),
    cancel:fn('qt3wd_cancel','int',['ulong'])};
  if(api.prepare()!==1)throw new Error('Transport preparation failed');
  boot={state:'armed',guiThread:tid,hwnd:hwndText};
  let starting=false;
  for(const name of ['PeekMessageW','PeekMessageA','GetMessageW','GetMessageA']) {
    const address=user.findExportByName(name);if(address===null)continue;
    hooks.push(Interceptor.attach(address,{onLeave() {
      if(starting||boot.state!=='armed'||Process.getCurrentThreadId()!==tid)return;
      starting=true;
      try {
        const result=api.start(hwnd.toUInt32(),actions?1:0);
        boot={state:result>0?'ready':'failed',guiThread:tid,startResult:result};
        send({event:'bootstrap',...boot});
      } catch(e) {boot={state:'failed',error:String(e)};send({event:'bootstrap',...boot});}
      setImmediate(()=>{for(const h of hooks)h.detach();hooks=[];});
    }}));
  }
  const post=new NativeFunction(user.getExportByName('PostMessageW'),'bool',['pointer','uint','pointer','pointer'],'stdcall');
  if(!post(hwnd,0,ptr(0),ptr(0)))throw new Error('Could not wake target GUI thread');
  return boot;
}
rpc.exports={
  inventory,
  begin,
  status(){return boot;},
  submit(request){if(boot.state!=='ready')throw new Error('Backend is not initialized');return api.submit(Memory.allocUtf8String(request));},
  poll(id){const buffer=Memory.alloc(262144);const state=api.poll(id,buffer,262144);return {state,reply:state===1?JSON.parse(buffer.readUtf8String()):null};},
  cancel(id){return api.cancel(id);},
  disarm(){for(const h of hooks)h.detach();hooks=[];return {state:'detached-hooks',backendRemainsLoaded:backend!==null};}
};
```

## FILE: native/backend.cpp

```cpp
// GPL-2.0-or-later. Experimental Qt3 widget backend; no upstream QtWebDriver
// server code is compiled here. Frida transports only this C ABI.
#include "backend.h"
#include <qapplication.h>
#include <qwidget.h>
#include <qwidgetlist.h>
#include <qobjectlist.h>
#include <qlineedit.h>
#include <qbutton.h>
#include <qcheckbox.h>
#include <qpopupmenu.h>
#include <qmenubar.h>
#include <qfiledialog.h>
#include <qlabel.h>
#include <qtimer.h>
#include <qevent.h>
#include <stdio.h>
#include <string.h>

// Present in this pinned threaded Qt3 build. A scalar getter lets bootstrap
// reject a non-Qt GUI thread without reading or calling a QWidget there.
extern Q_EXPORT Qt::HANDLE qt_get_application_thread_id();

enum { SLOTS=32, MAX_REQUEST=8192, MAX_REPLY=262144 };
struct Packet { unsigned long id; int state; DWORD queued,started; char request[MAX_REQUEST]; char reply[MAX_REPLY]; };
static Packet packets[SLOTS];
static CRITICAL_SECTION mutex;
static LONG prepared=0, ready=0;
static unsigned long sequence=0;
static Engine *engine=0;

static QString quote(const QString &s) {
    QString out="\"";
    for (uint i=0;i<s.length();++i) {
        ushort c=s[i].unicode();
        if (c=='"') out+="\\\"";
        else if (c=='\\') out+="\\\\";
        else if (c<32) out+=QString("\\u%1").arg(c,4,16).replace(' ','0');
        else out+=s[i];
    }
    return out+"\"";
}
static QString success(const QString &json) { return "{\"value\":"+json+"}"; }
static QString failure(const QString &code,const QString &message) {
    return "{\"error\":"+quote(code)+",\"message\":"+quote(message)+"}";
}
static QString flag(bool b) { return b?"true":"false"; }
static QString address(QObject *object) { return QString::number((unsigned long)object,16); }
static int hex(char c) { if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1; }
static QString decode(const QString &s) {
    QCString input=s.latin1(),out(input.length()+1); int n=0;
    for(uint i=0;i<input.length();++i) {
        if(input[i]=='%'&&i+2<input.length()&&hex(input[i+1])>=0&&hex(input[i+2])>=0) {out[n++]=char(hex(input[i+1])*16+hex(input[i+2]));i+=2;}
        else out[n++]=input[i];
    }
    out[n]=0; return QString::fromUtf8(out,n);
}
static QString normalized(QString s) {
    s=s.section('\t',0,0).stripWhiteSpace();
    QString out;
    for(uint i=0;i<s.length();++i) {
        if(s[i]=='&') { if(i+1<s.length()&&s[i+1]=='&'){out+='&';++i;} }
        else out+=s[i];
    }
    return out; // Ellipses are significant; do not silently conflate labels.
}
Engine::Engine(bool actions):QObject(qApp,"qt3webdriver.dispatcher"),next_(0),gui_(GetCurrentThreadId()),actions_(actions),destroyed_(0),dropped_(0) {
    nonce_=QString::number(GetCurrentProcessId())+"-"+QString::number(GetTickCount());
    QTimer *timer=new QTimer(this);
    connect(timer,SIGNAL(timeout()),this,SLOT(pump())); timer->start(10);
}
Engine::~Engine() { InterlockedExchange(&ready,0); }
QString Engine::add(QObject *object) {
    QString key=address(object),id=addresses_[key];
    if(!id.isEmpty()&&handles_.contains(id)&&!handles_[id].isNull()) return id;
    if(handles_.count()>=8192) return QString::null;
    id=nonce_+"-"+QString::number(++next_);
    handles_.insert(id,QGuardedPtr<QObject>(object)); addresses_.insert(key,id);
    connect(object,SIGNAL(destroyed(QObject*)),this,SLOT(destroyedObject(QObject*)));
    lifecycle("registered",id);
    return id;
}
void Engine::lifecycle(const QString &event,const QString &id) {
    if(events_.count()>=512){events_.pop_front();++dropped_;}
    events_.append("{\"event\":"+quote(event)+",\"id\":"+quote(id)+",\"guiThread\":"+QString::number(GetCurrentThreadId())+",\"tickMs\":"+QString::number(GetTickCount())+"}");
}
void Engine::destroyedObject(QObject *object) {
    // Do not read properties during destruction. QGuardedPtr owns invalidation.
    QString key=address(object);lifecycle("destroyed",addresses_[key]);
    addresses_.remove(key); ++destroyed_;
}
QObject *Engine::get(const QString &id,QString &error) {
    if(!handles_.contains(id)) {error="no such element";return 0;}
    if(handles_[id].isNull()) {error="stale element reference";return 0;}
    return (QObject*)handles_[id];
}
QString Engine::describe(QObject *object) {
    QGuardedPtr<QObject> guard(object);
    QString id=add(object);
    if(id.isNull()) return "null";
    QString out="{\"id\":"+quote(id)+",\"class\":"+quote(object->className())+",\"name\":"+quote(object->name());
    if(object->isWidgetType()) {
        QWidget *widget=(QWidget*)object;
        out+=",\"visible\":"+flag(widget->isVisible())+",\"enabled\":"+flag(widget->isEnabled());
        if(widget->isTopLevel()) out+=",\"caption\":"+quote(widget->caption())+",\"active\":"+flag(widget->isActiveWindow());
    }
    if(object->inherits("QLineEdit")) {
        QLineEdit *input=(QLineEdit*)object;
        bool secret=input->echoMode()!=QLineEdit::Normal;
        out+=",\"password\":"+flag(secret)+",\"readOnly\":"+flag(input->isReadOnly());
        if(!secret) out+=",\"text\":"+quote(input->text());
    } else if(object->inherits("QButton")) {
        out+=",\"text\":"+quote(((QButton*)object)->text());
        if(object->inherits("QCheckBox")) out+=",\"checked\":"+flag(((QCheckBox*)object)->isChecked());
    } else if(object->inherits("QLabel")) out+=",\"text\":"+quote(((QLabel*)object)->text());
    return out+"}";
}
void Engine::gather(QObject *root,const QString &parentId,int depth,QStringList &rows,bool &truncated) {
    if(!root||rows.count()>=512||depth>24) {truncated=true;return;}
    QGuardedPtr<QObject> guard(root);
    QString id=add(root);
    if(id.isNull()) {truncated=true;return;}
    // Bulk tree collection intentionally omits text values, including passwords.
    QString row="{\"id\":"+quote(id)+",\"parent\":"+quote(parentId)+",\"depth\":"+QString::number(depth)
        +",\"class\":"+quote(root->className())+",\"name\":"+quote(root->name());
    if(root->isWidgetType()) {QWidget *w=(QWidget*)root;row+=",\"visible\":"+flag(w->isVisible())+",\"enabled\":"+flag(w->isEnabled());}
    rows.append(row+"}");
    const QObjectList *children=root->children();
    if(!children)return;
    QPtrList<QObject> snapshot(*children);
    for(QObject *child=snapshot.first();child;child=snapshot.next()) {
        if(child->isWidgetType()&&((QWidget*)child)->isTopLevel()) continue; // Listed separately as a root.
        gather(child,id,depth+1,rows,truncated);
    }
}
bool Engine::actionable(QWidget *widget,QString &error) {
    if(!widget->isVisible()||!widget->isEnabled()){error="Element is hidden or disabled";return false;}
    QWidget *modal=QApplication::activeModalWidget();
    if(modal&&widget->topLevelWidget()!=modal) {error="Another modal window blocks this element";return false;}
    return true;
}
bool Engine::pressButton(QWidget *widget,QString &error) {
    if(!actionable(widget,error))return false;
    QGuardedPtr<QWidget> guard(widget);
    QKeyEvent down(QEvent::KeyPress,Qt::Key_Space,32,0);
    QApplication::sendEvent(widget,&down);
    if(guard.isNull()){error="Outcome unknown: destroyed during key press";return false;}
    QKeyEvent up(QEvent::KeyRelease,Qt::Key_Space,32,0);
    QApplication::sendEvent((QWidget*)guard,&up);
    return true; // Never access the receiver after activation callbacks.
}
QString Engine::menu(const QStringList &args) {
    if(args.count()<3)return failure("invalid argument","MENU requires a scope ID and path segments");
    QString error; QObject *scope=get(args[1],error);
    if(!scope)return failure(error,"Menu scope is unavailable");
    if(!scope->isWidgetType()||!actionable((QWidget*)scope,error))return failure("element not interactable","Menu scope is hidden, disabled, or blocked by a modal dialog");
    QObjectList *bars=scope->queryList("QMenuBar",0,false,true);
    if(bars->count()!=1) {delete bars;return failure("invalid selector","Scope must contain exactly one menu bar");}
    QGuardedPtr<QObject> owner(bars->first()); delete bars;
    QMenuData *data=(QMenuBar*)(QObject*)owner;
    for(uint part=2;part<args.count();++part) {
        if(owner.isNull())return failure("stale element reference","Menu owner was destroyed");
        int selected=-1,matches=0;
        for(uint index=0;index<data->count();++index) {
            int id=data->idAt(index); QMenuItem *item=data->findItem(id);
            if(item&&!item->isSeparator()&&normalized(data->text(id))==normalized(args[part])) {selected=id;++matches;}
        }
        if(!matches)return failure("no such element","Menu path segment is absent");
        if(matches!=1)return failure("invalid selector","Ambiguous menu path segment");
        if(!data->isItemEnabled(selected)||!data->isItemVisible(selected))return failure("element not interactable","Menu item is disabled or hidden");
        QMenuItem *item=data->findItem(selected);
        QGuardedPtr<QPopupMenu> next(item?item->popup():0);
        if(part+1<args.count()&&next.isNull())return failure("invalid selector","Intermediate menu segment is not a submenu");
        if(part+1==args.count()&&!next.isNull())return failure("invalid selector","Final menu segment is a submenu, not an action");
        data->activateItemAt(data->indexOf(selected)); // Show/populate submenu through Qt's normal behavior.
        if(part+1<args.count()) {
            if(next.isNull())return failure("stale element reference","Submenu replaced while opening; resolve again");
            owner=(QPopupMenu*)next; data=(QPopupMenu*)next;
        }
    }
    return success("{\"dispatched\":true,\"postconditionRequired\":true}");
}
QString Engine::execute(const QStringList &a) {
    if(GetCurrentThreadId()!=gui_)return failure("wrong thread","Command not on GUI thread");
    if(a.isEmpty())return failure("invalid argument","Missing command");
    QString command=a[0];
    if(command=="EVENTS"){
        QString result="{\"events\":["+events_.join(",")+"],\"dropped\":"+QString::number(dropped_)+"}";
        events_.clear();dropped_=0;return success(result);
    }
    if(command=="INFO")return success("{\"qt\":"+quote(qVersion())+",\"guiThread\":"+QString::number(gui_)
        +",\"qtApplicationThread\":"+QString::number((DWORD)qt_get_application_thread_id())
        +",\"currentThread\":"+QString::number(GetCurrentThreadId())+",\"actionsEnabled\":"+flag(actions_)
        +",\"registered\":"+QString::number(handles_.count())+",\"destroyed\":"+QString::number(destroyed_)+"}");
    if(command=="TREE") {
        QStringList rows; bool truncated=false;
        QWidgetList *roots=QApplication::topLevelWidgets();
        for(QWidget *w=roots->first();w;w=roots->next())gather(w,"",0,rows,truncated);
        delete roots;
        return success("{\"objects\":["+rows.join(",")+"],\"truncated\":"+flag(truncated)+"}");
    }
    if(command=="FIND"&&(a.count()==4||a.count()==6)) {
        QObject *scope=0;QString error;
        if(!a[1].isEmpty()){scope=get(a[1],error);if(!scope)return failure(error,"Scope unavailable");}
        QWidgetList *widgets=QApplication::allWidgets(); QObject *match=0;int matches=0;
        for(QWidget *w=widgets->first();w;w=widgets->next()) {
            bool inside=!scope;
            for(QObject *p=w;p&&!inside;p=p->parent()) if(p==scope)inside=true;
            bool selected=inside&&(a[2].isEmpty()||w->inherits(a[2].latin1()))&&(a[3].isEmpty()||QString(w->name())==a[3]);
            if(selected&&a.count()==6&&!a[4].isEmpty()) {
                QString text;
                if(w->inherits("QButton"))text=((QButton*)w)->text();
                else if(w->inherits("QLabel"))text=((QLabel*)w)->text();
                else if(w->inherits("QLineEdit")&&((QLineEdit*)w)->echoMode()==QLineEdit::Normal)text=((QLineEdit*)w)->text();
                selected=text==a[4];
            }
            if(selected&&a.count()==6&&!a[5].isEmpty())selected=w->isTopLevel()&&w->caption()==a[5];
            if(selected){match=w;++matches;}
        }
        delete widgets;
        if(!matches)return failure("no such element","No matching widget");
        if(matches!=1)return failure("invalid selector","Selector is ambiguous");
        QString id=add(match);if(id.isNull())return failure("resource limit","Registry full; restart the test process");
        return success(quote(id));
    }
    if(command=="DESCRIBE"&&a.count()==2){QString error;QObject *o=get(a[1],error);return o?success(describe(o)):failure(error,"Handle unavailable");}
    if(command=="MENU_ITEMS"&&a.count()==2) {
        QString error;QObject *o=get(a[1],error);if(!o)return failure(error,"Handle unavailable");
        QMenuData *menu=0;
        if(o->inherits("QPopupMenu"))menu=(QPopupMenu*)o;else if(o->inherits("QMenuBar"))menu=(QMenuBar*)o;
        if(!menu)return failure("invalid element state","Not a menu");
        QStringList rows;
        for(uint i=0;i<menu->count();++i){int id=menu->idAt(i);QMenuItem *item=menu->findItem(id);
            rows.append("{\"id\":"+QString::number(id)+",\"index\":"+QString::number(i)+",\"text\":"+quote(menu->text(id))
                +",\"enabled\":"+flag(menu->isItemEnabled(id))+",\"submenu\":"+flag(item&&item->popup())+"}");}
        return success("["+rows.join(",")+"]");
    }
    if(!actions_)return failure("actions disabled","Session was started in read-only mode");
    if(command=="MENU")return menu(a);
    if(a.count()<2)return failure("invalid argument","Action requires an element ID");
    QString error;QObject *object=get(a[1],error);
    if(!object)return failure(error,"Handle unavailable");
    if(!object->isWidgetType())return failure("invalid element state","Object is not a widget");
    QGuardedPtr<QWidget> guard((QWidget*)object); QWidget *widget=(QWidget*)object;
    if(command=="WINDOW"&&a.count()==2) {
        if(!widget->isTopLevel())return failure("invalid element state","Expected a top-level window");
        QWidget *modal=QApplication::activeModalWidget();
        if(modal&&modal!=widget)return failure("element not interactable","Another modal window is active");
        if(widget->isMinimized())widget->showNormal();else widget->show();
        if(guard.isNull())return failure("outcome unknown","Destroyed during show");
        guard->raise();if(guard.isNull())return failure("outcome unknown","Destroyed during raise");
        guard->setActiveWindow();
        return success("{\"dispatched\":true}");
    }
    if(!actionable(widget,error))return failure("element not interactable",error);
    if(command=="CLICK"&&a.count()==2) {
        if(!object->inherits("QButton"))return failure("invalid element state","Expected QButton");
        return pressButton(widget,error)?success("{\"dispatched\":true,\"postconditionRequired\":true}"):failure("outcome unknown",error);
    }
    if(command=="FILL"&&a.count()==3) {
        if(!object->inherits("QLineEdit"))return failure("invalid element state","Input adapter supports QLineEdit");
        QLineEdit *input=(QLineEdit*)object;
        if(input->isReadOnly())return failure("invalid element state","Input is read-only");
        input->setText(a[2]);
        if(guard.isNull())return failure("outcome unknown","Destroyed during textChanged");
        return input->text()==a[2]?success("{\"verified\":true}"):failure("outcome unknown","Input value changed during callback");
    }
    if(command=="CHECK"&&a.count()==3) {
        if(!object->inherits("QCheckBox")||(a[2]!="true"&&a[2]!="false"))return failure("invalid argument","CHECK expects a checkbox and true/false");
        QCheckBox *box=(QCheckBox*)object;bool desired=a[2]=="true";
        if(box->isTristate())return failure("unsupported operation","Tristate checkbox needs an explicit state adapter");
        if(box->isChecked()==desired)return success("{\"verified\":true,\"changed\":false}");
        if(!pressButton(box,error)||guard.isNull())return failure("outcome unknown","Checkbox changed or disappeared during activation");
        return box->isChecked()==desired?success("{\"verified\":true,\"changed\":true}"):failure("outcome unknown","Checkbox postcondition failed");
    }
    if(command=="FILE_PATH"&&a.count()==3) {
        if(!object->inherits("QFileDialog"))return failure("unsupported operation","Expected a Qt3 QFileDialog; native Windows dialogs need another adapter");
        QFileDialog *dialog=(QFileDialog*)object;dialog->setSelection(a[2]);
        if(guard.isNull())return failure("outcome unknown","File dialog destroyed during selection");
        return success("{\"selectedFile\":"+quote(dialog->selectedFile())+",\"postconditionRequired\":true}");
    }
    if(command=="FILE_ACCEPT"&&a.count()==2) {
        if(!object->inherits("QFileDialog"))return failure("unsupported operation","Expected a Qt3 QFileDialog");
        // Use the dialog's real default button path, including its validation.
        QKeyEvent enter(QEvent::KeyPress,Qt::Key_Return,13,0);
        QApplication::sendEvent(widget,&enter);
        return success("{\"dispatched\":true,\"postconditionRequired\":true}");
    }
    if(command=="DIALOG_CANCEL"&&a.count()==2) {
        if(!object->inherits("QDialog"))return failure("invalid element state","Expected QDialog");
        QKeyEvent escape(QEvent::KeyPress,Qt::Key_Escape,27,0);QApplication::sendEvent(widget,&escape);
        return success("{\"dispatched\":true}");
    }
    return failure("unsupported operation","Command/type/argument combination is unsupported");
}
void Engine::pump() {
    int selected=-1;char request[MAX_REQUEST];unsigned long id=0;DWORD queued=0,started=0;
    EnterCriticalSection(&mutex);
    for(int i=0;i<SLOTS;++i)if(packets[i].state==1){selected=i;break;}
    if(selected>=0){Packet &p=packets[selected];p.state=2;p.started=GetTickCount();id=p.id;queued=p.queued;started=p.started;strcpy(request,p.request);}
    LeaveCriticalSection(&mutex);
    if(selected<0)return;
    // A nested modal loop must be able to process a later dialog command.
    QTimer::singleShot(0,this,SLOT(pump()));
    QStringList args=QStringList::split('\t',QString::fromLatin1(request),true);
    for(uint i=0;i<args.count();++i)args[i]=decode(args[i]);
    QString result=execute(args);
    QString wrapped="{\"requestId\":"+QString::number(id)+",\"guiThread\":"+QString::number(gui_)
        +",\"queueMs\":"+QString::number((DWORD)(started-queued))+",\"executeMs\":"+QString::number((DWORD)(GetTickCount()-started))
        +",\"result\":"+result+"}";
    QCString bytes=wrapped.utf8();
    EnterCriticalSection(&mutex);
    Packet &packet=packets[selected];
    if(bytes.length()>=MAX_REPLY)strcpy(packet.reply,"{\"result\":{\"error\":\"resource limit\",\"message\":\"Reply too large\"}}");
    else strcpy(packet.reply,bytes.data());
    packet.state=3;
    LeaveCriticalSection(&mutex);
}

extern "C" __declspec(dllexport) int __cdecl qt3wd_prepare() {
    LONG state=InterlockedCompareExchange(&prepared,-1,0);
    if(state==1)return 1;if(state!=0)return 0;
    InitializeCriticalSection(&mutex);InterlockedExchange(&prepared,1);return 1;
}
extern "C" __declspec(dllexport) int __cdecl qt3wd_start(unsigned long hwnd,int actions) {
    if(prepared!=1||!qApp||sizeof(void*)!=4)return -1;
    DWORD pid=0,thread=GetWindowThreadProcessId((HWND)hwnd,&pid);
    if(!thread||pid!=GetCurrentProcessId()||thread!=GetCurrentThreadId())return -2;
    if((DWORD)qt_get_application_thread_id()!=GetCurrentThreadId())return -3;
    if(ready)return 2; // Existing backend retains its original read/action mode.
    engine=new Engine(actions!=0);InterlockedExchange(&ready,1);return 1;
}
extern "C" __declspec(dllexport) unsigned long __cdecl qt3wd_submit(const char *request) {
    if(prepared!=1||ready!=1||!request||strlen(request)>=MAX_REQUEST)return 0;
    EnterCriticalSection(&mutex);unsigned long id=0;
    for(int i=0;i<SLOTS;++i)if(packets[i].state==0){Packet &p=packets[i];id=++sequence;if(!id)id=++sequence;p.id=id;p.state=1;p.queued=GetTickCount();strcpy(p.request,request);break;}
    LeaveCriticalSection(&mutex);return id;
}
extern "C" __declspec(dllexport) int __cdecl qt3wd_poll(unsigned long id,char *output,unsigned long capacity) {
    if(prepared!=1||!output)return -1;int result=-1;
    EnterCriticalSection(&mutex);
    for(int i=0;i<SLOTS;++i)if(packets[i].id==id&&packets[i].state){Packet &p=packets[i];result=0;
        if(p.state==3){if(strlen(p.reply)+1>capacity)result=-2;else {strcpy(output,p.reply);p.state=0;result=1;}}break;}
    LeaveCriticalSection(&mutex);return result;
}
extern "C" __declspec(dllexport) int __cdecl qt3wd_cancel(unsigned long id) {
    if(prepared!=1)return -1;int result=-1;
    EnterCriticalSection(&mutex);
    for(int i=0;i<SLOTS;++i)if(packets[i].id==id&&packets[i].state){Packet &p=packets[i];
        if(p.state==1){p.state=0;result=1;}else result=0;break;}
    LeaveCriticalSection(&mutex);return result; // 0: may have run; reconcile, never replay.
}
```

## FILE: native/backend.h

```cpp
#ifndef QT3WD_BACKEND_H
#define QT3WD_BACKEND_H
#include <qobject.h>
#include <qguardedptr.h>
#include <qmap.h>
#include <qstringlist.h>
#include <windows.h>

class Engine : public QObject {
    Q_OBJECT
public:
    Engine(bool actions);
    ~Engine();
    QString execute(const QStringList &args);
public slots:
    void pump();
    void destroyedObject(QObject *object);
private:
    QString add(QObject *object);
    QObject *get(const QString &id, QString &error);
    QString describe(QObject *object);
    QString menu(const QStringList &args);
    bool actionable(QWidget *widget, QString &error);
    bool pressButton(QWidget *widget, QString &error);
    void lifecycle(const QString &event,const QString &id);
    void gather(QObject *root, const QString &parentId, int depth, QStringList &rows, bool &truncated);
    QMap<QString,QGuardedPtr<QObject> > handles_;
    QMap<QString,QString> addresses_;
    QString nonce_;
    unsigned long next_;
    DWORD gui_;
    bool actions_;
    unsigned long destroyed_;
    QStringList events_;
    unsigned long dropped_;
};
#endif
```

## FILE: native/backend.pro

```text
TEMPLATE = lib
TARGET = qt3webdriver
VERSION =
CONFIG += qt dll thread release warn_on
CONFIG -= debug
SOURCES = backend.cpp
HEADERS = backend.h
DESTDIR = .
OBJECTS_DIR = obj
MOC_DIR = moc
QMAKE_LFLAGS += -Wl,--kill-at
```

## FILE: lab/fixture.cpp

```cpp
#include "fixture.h"
#include <qapplication.h>
#include <qlineedit.h>
#include <qpushbutton.h>
#include <qcheckbox.h>
#include <qlabel.h>
#include <qpopupmenu.h>
#include <qmenubar.h>
#include <qfiledialog.h>
#include <qtimer.h>
#include <stdio.h>
Fixture::Fixture():QMainWindow(0,"fixtureWindow"),clicks_(0),generation_(0),revision_(0) {
    setCaption("Qt3 native backend fixture");resize(640,300);
    input_=new QLineEdit(this,"input");input_->setGeometry(20,55,300,28);input_->setText("initial");
    QLineEdit *password=new QLineEdit(this,"password");password->setEchoMode(QLineEdit::Password);
    password->setText("DO-NOT-LOG-PASSWORD");password->setGeometry(340,55,260,28);
    QPushButton *button=new QPushButton("Activate",this,"button");button->setGeometry(20,100,130,30);
    connect(button,SIGNAL(clicked()),this,SLOT(activated()));
    QPushButton *replace=new QPushButton("Replace input",this,"replace");replace->setGeometry(160,100,150,30);
    connect(replace,SIGNAL(clicked()),this,SLOT(replaceInput()));
    QPushButton *file=new QPushButton("Open file",this,"file");file->setGeometry(320,100,130,30);
    connect(file,SIGNAL(clicked()),this,SLOT(openFile()));
    QCheckBox *check=new QCheckBox("Enabled option",this,"checkbox");check->setGeometry(20,145,250,30);
    status_=new QLabel("ready",this,"status");status_->setGeometry(20,200,600,50);
    QPopupMenu *fileMenu=new QPopupMenu(this,"fileMenu");
    tools_=new QPopupMenu(this,"toolsMenu");
    tools_->insertItem("Mark",this,SLOT(marked()),0,77);
    tools_->insertItem("Open...",this,SLOT(openFile()),0,91);
    connect(tools_,SIGNAL(aboutToShow()),this,SLOT(populate()));
    fileMenu->insertItem("Tools",tools_);
    fileMenu->insertItem("Open...",this,SLOT(openFile()));
    menuBar()->setName("menuBar");menuBar()->insertItem("&File",fileMenu);
    QTimer *timer=new QTimer(this);connect(timer,SIGNAL(timeout()),this,SLOT(tick()));timer->start(50);
}
void Fixture::activated(){status_->setText(QString("clicks:%1").arg(++clicks_));}
void Fixture::replaceInput(){delete input_;input_=new QLineEdit(this,"input");input_->setGeometry(20,55,300,28);input_->setText(QString("generation:%1").arg(++generation_));input_->show();}
void Fixture::marked(){status_->setText(QString("marked:%1").arg(revision_));}
void Fixture::populate(){tools_->removeItem(123);tools_->insertItem(QString("Revision %1").arg(++revision_),123,0);tools_->setItemEnabled(123,false);}
void Fixture::tick(){}
void Fixture::openFile(){
    QFileDialog dialog(this,"fileDialog",true);dialog.setMode(QFileDialog::ExistingFile);
    if(dialog.exec()==QDialog::Accepted)status_->setText("file:"+dialog.selectedFile());
    else status_->setText("file:cancelled");
}
int main(int argc,char **argv){QApplication app(argc,argv);Fixture window;app.setMainWidget(&window);window.setCaption("Qt3 native backend fixture");window.show();printf("fixture-ready\n");fflush(stdout);return app.exec();}
```

## FILE: lab/fixture.h

```cpp
#ifndef QT3WD_FIXTURE_H
#define QT3WD_FIXTURE_H
#include <qmainwindow.h>
class QLineEdit;
class QLabel;
class QPopupMenu;
class Fixture : public QMainWindow {
    Q_OBJECT
public:
    Fixture();
public slots:
    void activated();
    void replaceInput();
    void openFile();
    void marked();
    void populate();
    void tick();
private:
    QLineEdit *input_;
    QLabel *status_;
    QPopupMenu *tools_;
    int clicks_,generation_,revision_;
};
#endif
```

## FILE: lab/fixture.pro

```text
TEMPLATE = app
TARGET = qt3-fixture
CONFIG += qt console thread release warn_on
CONFIG -= debug
SOURCES = fixture.cpp
HEADERS = fixture.h
DESTDIR = .
OBJECTS_DIR = obj
MOC_DIR = moc
```

## FILE: scripts/build_backend.py

```python
"""Build the minimal backend using an already available, approved Qt3 x86 SDK.

This script builds the MinGW profile only. It does not load anything into a
target app, download dependencies, or replace target application libraries.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def build_project(source, project, artifact, destination, sdk, compiler, work, env, evidence):
    work.mkdir(parents=True, exist_ok=True)
    for file in source.iterdir():
        if file.is_file():
            shutil.copy2(file, work / file.name)
    with evidence.open('w', encoding='utf-8') as log:
        for command in [[str(sdk / 'bin' / 'qmake.exe'), project],
                        [str(compiler / 'bin' / 'mingw32-make.exe')]]:
            print(subprocess.list2cmdline(command), flush=True)
            subprocess.run(command, cwd=work, env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(work / artifact, destination / artifact)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--with-fixture', action='store_true',
                        help='Also build the optional self-owned Qt3 fixture for validation')
    args = parser.parse_args()
    sdk, compiler, work = args.sdk.resolve(), args.compiler.resolve(), args.work_dir.resolve()
    needed = [sdk / 'bin' / 'qmake.exe', sdk / 'bin' / 'moc.exe',
              sdk / 'lib' / 'qt-mt.dll', sdk / 'lib' / 'libqt-mt.a',
              compiler / 'bin' / 'g++.exe', compiler / 'bin' / 'mingw32-make.exe',
              compiler / 'bin' / 'mingwm10.dll']
    for path in needed:
        if not path.is_file():
            raise FileNotFoundError(f'Required approved SDK/tool file is missing: {path}')
    system = Path(os.environ.get('SYSTEMROOT', r'C:\Windows'))
    env = os.environ.copy()
    env.update(QTDIR=str(sdk), QMAKESPEC='win32-g++',
               COMSPEC=str(system / 'System32' / 'cmd.exe'),
               PATH=';'.join(map(str, [compiler / 'bin', sdk / 'bin', system / 'System32', system])))
    env.pop('MAKEFLAGS', None)
    evidence = ROOT / 'build-logs'
    evidence.mkdir(exist_ok=True)
    runtime = ROOT / 'runtime'
    build_project(ROOT / 'native', 'backend.pro', 'qt3webdriver.dll', runtime,
                  sdk, compiler, work / 'backend', env, evidence / 'backend.log')
    profile = {
        'profile': 'qtwin-p8-mingw345-rebuilt',
        'qt_sha256': sha(sdk / 'lib' / 'qt-mt.dll'),
        'artifacts': {
            'qt3webdriver.dll': sha(runtime / 'qt3webdriver.dll'),
            'mingwm10.dll': sha(compiler / 'bin' / 'mingwm10.dll'),
        },
    }
    (ROOT / 'profiles').mkdir(exist_ok=True)
    (ROOT / 'profiles' / 'lab.json').write_text(json.dumps(profile, indent=2), encoding='utf-8')
    if args.with_fixture:
        fixture = ROOT / 'lab-runtime'
        build_project(ROOT / 'lab', 'fixture.pro', 'qt3-fixture.exe', fixture,
                      sdk, compiler, work / 'fixture', env, evidence / 'fixture.log')
        shutil.copy2(sdk / 'lib' / 'qt-mt.dll', fixture / 'qt-mt.dll')
        shutil.copy2(compiler / 'bin' / 'mingwm10.dll', fixture / 'mingwm10.dll')
    (evidence / 'profile.json').write_text(json.dumps(profile, indent=2), encoding='utf-8')
    print(json.dumps(profile, indent=2))
    print('Minimal runtime: runtime/qt3webdriver.dll; use python/, agent/, profiles/, requirements.txt and notices.')
    print('Do not copy lab Qt/runtime DLLs into a target application directory.')


if __name__ == '__main__':
    main()
```

## FILE: scripts/build_lab_sdk.py

```python
"""Build the pinned Windows x86 Qt3 lab using local, portable dependencies.

Requires Windows x64, Python 3.10+, curl.exe and tar.exe. No installer is run.
An unused drive letter is temporarily mapped to the work directory and removed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
GCC_BASE = "https://downloads.sourceforge.net/project/mingw/MinGW/Base/gcc/Version3/Current%20Release_%20gcc-3.4.5-20060117-3/"
INPUTS = {
    "qt3-source.7z": ("https://downloads.sourceforge.net/project/qtwin/Unofficial%20Qtwin/qt-win-3.3.x-8/qt-3.3.x-p8.7z", "f8b50f6cc8ada5d135b5c80dc293e438c2fc61277cff1908a8d6de00e70b22b1"),
    "mingw-3.4.2.exe": ("https://downloads.sourceforge.net/project/qwinreloaded/MinGW-3.4.2.exe", "9c58a17b2f7c2e674e7ac1e542f8be433c8e59a6c03d94249fb88aa0366a3fa2"),
    "gcc-core-3.4.5.tar.gz": (GCC_BASE + "gcc-core-3.4.5-20060117-3.tar.gz", "be73c9428664b891fd45124de5ca78286cae2a6515890838f1347f77d21852ca"),
    "gcc-cpp-3.4.5.tar.gz": (GCC_BASE + "gcc-g%2B%2B-3.4.5-20060117-3.tar.gz", "cb1815cea431d4b5d2809743c617253ff5c1578876ef01a476550a082e484f08"),
    "7z-extra.7z": ("https://www.7-zip.org/a/7z2301-extra.7z", "db3a1cbe57a26fac81b65c6a2d23feaecdeede3e4c1fe8fb93a7b91d72d1094c"),
    "7z2301-x64.exe": ("https://www.7-zip.org/a/7z2301-x64.exe", "26cb6e9f56333682122fafe79dbcdfd51e9f47cc7217dccd29ac6fc33b5598cd"),
}
CONFIGURE = ["-release", "-shared", "-thread", "-no-opengl", "-no-tablet", "-no-sound",
             "-no-imgfmt-mng", "-no-imgfmt-jpeg", "-fast", "-nobuild"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, *, cwd=None, env=None, log=None):
    print("Running:", subprocess.list2cmdline([str(x) for x in command]), flush=True)
    if log:
        with Path(log).open("w", encoding="utf-8") as output:
            subprocess.run(command, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT, check=True)
    else:
        subprocess.run(command, cwd=cwd, env=env, check=True)


def safe_tar(archive, destination):
    listing = subprocess.check_output(["tar.exe", "-tf", str(archive)], text=True)
    for name in listing.splitlines():
        path = PurePosixPath(name.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or ":" in name:
            raise ValueError(f"Unsafe archive path: {name}")
    destination.mkdir(parents=True, exist_ok=True)
    run(["tar.exe", "-xf", str(archive), "-C", str(destination)])


def prepare(work, cache, allow_download=False):
    cache.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in INPUTS.items():
        target = cache / name
        bundled = ROOT / "vendor" / name
        if not target.exists() and bundled.exists():
            shutil.copy2(bundled, target)
        if not target.exists():
            if not allow_download:
                raise FileNotFoundError(f"Approved cache is missing {name}. Expected URL: {url}; SHA-256: {expected}")
            run(["curl.exe", "-L", "--fail", "--retry", "2", "--max-time", "600", "-o", str(target), url])
        if sha(target) != expected:
            raise ValueError(f"SHA-256 mismatch for {target}; do not use this artifact")
    if (work / "deps").exists():
        raise ValueError("Prepare requires a new work directory; choose another --work-dir (no files are deleted)")
    deps = work / "deps"
    safe_tar(cache / "7z-extra.7z", deps / "7zip")
    run([str(deps / "7zip" / "7za.exe"), "x", str(cache / "7z2301-x64.exe"), "-o" + str(deps / "7zip-full"), "-y"])
    run([str(deps / "7zip-full" / "7z.exe"), "x", str(cache / "mingw-3.4.2.exe"), "-o" + str(deps / "mingw345"), "-y"])
    # Keep headers/binutils/runtime from the original bundle; replace BOTH GCC
    # core and C++ with their matching upstream 3.4.5 packages.
    safe_tar(cache / "gcc-core-3.4.5.tar.gz", deps / "mingw345")
    safe_tar(cache / "gcc-cpp-3.4.5.tar.gz", deps / "mingw345")
    safe_tar(cache / "qt3-source.7z", deps)
    source = deps / "qt-3.3.x-p8" / "src" / "qt.pro"
    text = source.read_text()
    text, count = re.subn(r"(?m)^VERSION\s*= 3\s*$", "VERSION =", text, count=1)
    if count != 1:
        raise ValueError("Qt DLL naming patch did not match the pinned source")
    text += "\n# Lab: disabled sound must not generate meta-object code for absent QSound.\nHEADERS -= $$KERNEL_H/qsound.h\n"
    source.write_text(text, encoding="utf-8")
    (work / "prepared.json").write_text(json.dumps({name: values[1] for name, values in INPUTS.items()}, indent=2))



def build_sdk(work, drive):
    letter = drive.upper().rstrip(':')
    if not re.fullmatch('[D-Y]', letter):
        raise ValueError('Choose an unused drive letter D through Y')
    mapping = letter + ':'
    if Path(mapping + '\\').exists():
        raise ValueError(f'{mapping} is in use; choose another --drive')
    evidence = ROOT / 'build-logs' / 'sdk'
    evidence.mkdir(parents=True, exist_ok=True)
    run(['subst.exe', mapping, str(work)])
    try:
        base = Path(mapping + '\\')
        sdk = base / 'deps' / 'qt-3.3.x-p8'
        compiler = base / 'deps' / 'mingw345' / 'bin'
        system = Path(os.environ.get('SYSTEMROOT', r'C:\Windows'))
        env = os.environ.copy()
        env.update(QTDIR=str(sdk), QMAKESPEC='win32-g++',
                   COMSPEC=str(system / 'System32' / 'cmd.exe'),
                   PATH=';'.join(map(str, [compiler, sdk / 'bin', system / 'System32', system])))
        env.pop('MAKEFLAGS', None)
        run([str(compiler / 'g++.exe'), '--version'], env=env, log=evidence / 'compiler.log')
        smoke = base / 'compiler-smoke.cpp'
        smoke.write_text('#include <iostream>\nint main(){std::cout << "compiler-ok" << std::endl;}\n')
        run([str(compiler / 'g++.exe'), str(smoke), '-o', str(base / 'compiler-smoke.exe')], env=env)
        run([str(base / 'compiler-smoke.exe')], env=env, log=evidence / 'compiler-smoke.log')
        if not (sdk / '.qmake.cache').exists():
            run([str(system / 'System32' / 'cmd.exe'), '/d', '/c', 'configure-mingw.bat', *CONFIGURE],
                cwd=sdk, env=env, log=evidence / 'configure.log')
        run([str(compiler / 'mingw32-make.exe'), 'sub-src'],
            cwd=sdk, env=env, log=evidence / 'qt-build.log')
        if not (sdk / 'lib' / 'qt-mt.dll').is_file():
            raise RuntimeError('Qt did not emit qt-mt.dll; inspect build logs')
        manifest = {'inputs': {name: {'url': url, 'sha256': digest}
                               for name, (url, digest) in INPUTS.items()},
                    'configure': CONFIGURE,
                    'qt_sha256': sha(sdk / 'lib' / 'qt-mt.dll')}
        (evidence / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    finally:
        run(['subst.exe', mapping, '/d'])
    print('SDK:', work / 'deps' / 'qt-3.3.x-p8')
    print('Compiler:', work / 'deps' / 'mingw345')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build the self-owned Qt3 lab SDK from approved pinned artifacts')
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--drive', default='Q')
    parser.add_argument('--allow-download', action='store_true',
                        help='Use only when fetching these external dependencies is explicitly approved')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    work, cache = args.work_dir.resolve(), args.cache.resolve()
    work.mkdir(parents=True, exist_ok=True)
    if args.resume:
        marker = work / 'prepared.json'
        expected = {name: value[1] for name, value in INPUTS.items()}
        if not marker.is_file() or json.loads(marker.read_text()) != expected:
            raise ValueError('Resume requires a matching prepared.json from this recipe')
    else:
        prepare(work, cache, args.allow_download)
    build_sdk(work, args.drive)
```

## FILE: scripts/smoke_lab.py

```python
"""Exercise the rebuilt minimal kit against ONLY its own optional lab fixture."""
from pathlib import Path
import json
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from qt3wd import Driver, Trace, BackendError


def main():
    executable = ROOT / 'lab-runtime' / 'qt3-fixture.exe'
    if not executable.is_file():
        raise FileNotFoundError('Build with --with-fixture first. This smoke test never accepts a production PID.')
    evidence = ROOT / 'build-logs' / 'smoke'
    evidence.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen([str(executable)], cwd=executable.parent, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    driver = None
    opening = None
    errors = []
    try:
        assert process.stdout.readline() == b'fixture-ready\r\n'
        driver = Driver(Trace(evidence), pid=process.pid, actions=True)
        window = driver.locator(name='fixtureWindow')
        window.activate()
        input_field = driver.locator(name='input', scope=window)
        input_field.fill('rebuilt-minimal-ok')
        assert input_field.describe()['text'] == 'rebuilt-minimal-ok'
        driver.locator(name='button').click()
        driver.locator(name='status').wait(lambda state: state['text'] == 'clicks:1')
        box = driver.locator(name='checkbox')
        assert box.check(True)['changed']
        assert box.describe()['checked']
        assert box.check(True)['changed'] is False
        window.menu('File', 'Tools', 'Mark')
        driver.locator(name='status').wait(lambda state: state['text'].startswith('marked:'))
        old = input_field.resolve()
        driver.locator(name='replace').click()
        try:
            old.describe()
            raise AssertionError('Old explicit handle was not stale')
        except BackendError as error:
            assert error.code == 'stale element reference'
        assert input_field.resolve().id != old.id

        def open_dialog():
            try:
                window.menu('File', 'Tools', 'Open...', timeout=15)
            except Exception as error:
                errors.append(str(error))
        sample = (evidence / 'synthetic-input.txt').resolve()
        sample.write_text('Synthetic lab data only', encoding='utf-8')
        opening = threading.Thread(target=open_dialog)
        opening.start()
        dialog = driver.locator(name='fileDialog', class_name='QFileDialog')
        dialog.resolve()
        dialog.file_path(sample)
        dialog.accept_file()
        opening.join(5)
        assert not opening.is_alive() and not errors, errors
        result = driver.locator(name='status').wait(lambda state: state['text'].startswith('file:'))
        assert Path(result['text'][5:]).resolve() == sample
        assert 'text' not in driver.locator(name='password').describe()
        info = driver.call('INFO')
        assert info['guiThread'] == info['qtApplicationThread'] == info['currentThread']
        driver.drain_events()
        (evidence / 'result.json').write_text(json.dumps({'passed': True, 'qt': info['qt'],
            'controls': ['window', 'button', 'input', 'checkbox', 'menu', 'submenu', 'Qt3 file dialog'],
            'staleHandleVerified': True}, indent=2), encoding='utf-8')
        print('PASS: rebuilt minimal kit and synthetic controls')
    finally:
        if opening and opening.is_alive() and driver:
            try:
                driver.locator(name='fileDialog').cancel_dialog()
            except Exception:
                pass
            opening.join(3)
        if driver:
            driver.close()
        process.terminate()  # Only the dedicated fixture launched above.
        process.wait(timeout=5)
        stderr = process.stderr.read().decode(errors='replace')
        (evidence / 'fixture-stderr.log').write_text(stderr, encoding='utf-8')
        process.stdout.close()
        process.stderr.close()
        if stderr:
            raise RuntimeError(stderr)


if __name__ == '__main__':
    main()
```

## FILE: LICENSE

```text
		    GNU GENERAL PUBLIC LICENSE
		       Version 2, June 1991

 Copyright (C) 1989, 1991 Free Software Foundation, Inc.
     59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.

			    Preamble

  The licenses for most software are designed to take away your
freedom to share and change it.  By contrast, the GNU General Public
License is intended to guarantee your freedom to share and change free
software--to make sure the software is free for all its users.  This
General Public License applies to most of the Free Software
Foundation's software and to any other program whose authors commit to
using it.  (Some other Free Software Foundation software is covered by
the GNU Library General Public License instead.)  You can apply it to
your programs, too.

  When we speak of free software, we are referring to freedom, not
price.  Our General Public Licenses are designed to make sure that you
have the freedom to distribute copies of free software (and charge for
this service if you wish), that you receive source code or can get it
if you want it, that you can change the software or use pieces of it
in new free programs; and that you know you can do these things.

  To protect your rights, we need to make restrictions that forbid
anyone to deny you these rights or to ask you to surrender the rights.
These restrictions translate to certain responsibilities for you if you
distribute copies of the software, or if you modify it.

  For example, if you distribute copies of such a program, whether
gratis or for a fee, you must give the recipients all the rights that
you have.  You must make sure that they, too, receive or can get the
source code.  And you must show them these terms so they know their
rights.

  We protect your rights with two steps: (1) copyright the software, and
(2) offer you this license which gives you legal permission to copy,
distribute and/or modify the software.

  Also, for each author's protection and ours, we want to make certain
that everyone understands that there is no warranty for this free
software.  If the software is modified by someone else and passed on, we
want its recipients to know that what they have is not the original, so
that any problems introduced by others will not reflect on the original
authors' reputations.

  Finally, any free program is threatened constantly by software
patents.  We wish to avoid the danger that redistributors of a free
program will individually obtain patent licenses, in effect making the
program proprietary.  To prevent this, we have made it clear that any
patent must be licensed for everyone's free use or not licensed at all.

  The precise terms and conditions for copying, distribution and
modification follow.

		    GNU GENERAL PUBLIC LICENSE
   TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION

  0. This License applies to any program or other work which contains
a notice placed by the copyright holder saying it may be distributed
under the terms of this General Public License.  The "Program", below,
refers to any such program or work, and a "work based on the Program"
means either the Program or any derivative work under copyright law:
that is to say, a work containing the Program or a portion of it,
either verbatim or with modifications and/or translated into another
language.  (Hereinafter, translation is included without limitation in
the term "modification".)  Each licensee is addressed as "you".

Activities other than copying, distribution and modification are not
covered by this License; they are outside its scope.  The act of
running the Program is not restricted, and the output from the Program
is covered only if its contents constitute a work based on the
Program (independent of having been made by running the Program).
Whether that is true depends on what the Program does.

  1. You may copy and distribute verbatim copies of the Program's
source code as you receive it, in any medium, provided that you
conspicuously and appropriately publish on each copy an appropriate
copyright notice and disclaimer of warranty; keep intact all the
notices that refer to this License and to the absence of any warranty;
and give any other recipients of the Program a copy of this License
along with the Program.

You may charge a fee for the physical act of transferring a copy, and
you may at your option offer warranty protection in exchange for a fee.

  2. You may modify your copy or copies of the Program or any portion
of it, thus forming a work based on the Program, and copy and
distribute such modifications or work under the terms of Section 1
above, provided that you also meet all of these conditions:

    a) You must cause the modified files to carry prominent notices
    stating that you changed the files and the date of any change.

    b) You must cause any work that you distribute or publish, that in
    whole or in part contains or is derived from the Program or any
    part thereof, to be licensed as a whole at no charge to all third
    parties under the terms of this License.

    c) If the modified program normally reads commands interactively
    when run, you must cause it, when started running for such
    interactive use in the most ordinary way, to print or display an
    announcement including an appropriate copyright notice and a
    notice that there is no warranty (or else, saying that you provide
    a warranty) and that users may redistribute the program under
    these conditions, and telling the user how to view a copy of this
    License.  (Exception: if the Program itself is interactive but
    does not normally print such an announcement, your work based on
    the Program is not required to print an announcement.)

These requirements apply to the modified work as a whole.  If
identifiable sections of that work are not derived from the Program,
and can be reasonably considered independent and separate works in
themselves, then this License, and its terms, do not apply to those
sections when you distribute them as separate works.  But when you
distribute the same sections as part of a whole which is a work based
on the Program, the distribution of the whole must be on the terms of
this License, whose permissions for other licensees extend to the
entire whole, and thus to each and every part regardless of who wrote it.

Thus, it is not the intent of this section to claim rights or contest
your rights to work written entirely by you; rather, the intent is to
exercise the right to control the distribution of derivative or
collective works based on the Program.

In addition, mere aggregation of another work not based on the Program
with the Program (or with a work based on the Program) on a volume of
a storage or distribution medium does not bring the other work under
the scope of this License.

  3. You may copy and distribute the Program (or a work based on it,
under Section 2) in object code or executable form under the terms of
Sections 1 and 2 above provided that you also do one of the following:

    a) Accompany it with the complete corresponding machine-readable
    source code, which must be distributed under the terms of Sections
    1 and 2 above on a medium customarily used for software interchange; or,

    b) Accompany it with a written offer, valid for at least three
    years, to give any third party, for a charge no more than your
    cost of physically performing source distribution, a complete
    machine-readable copy of the corresponding source code, to be
    distributed under the terms of Sections 1 and 2 above on a medium
    customarily used for software interchange; or,

    c) Accompany it with the information you received as to the offer
    to distribute corresponding source code.  (This alternative is
    allowed only for noncommercial distribution and only if you
    received the program in object code or executable form with such
    an offer, in accord with Subsection b above.)

The source code for a work means the preferred form of the work for
making modifications to it.  For an executable work, complete source
code means all the source code for all modules it contains, plus any
associated interface definition files, plus the scripts used to
control compilation and installation of the executable.  However, as a
special exception, the source code distributed need not include
anything that is normally distributed (in either source or binary
form) with the major components (compiler, kernel, and so on) of the
operating system on which the executable runs, unless that component
itself accompanies the executable.

If distribution of executable or object code is made by offering
access to copy from a designated place, then offering equivalent
access to copy the source code from the same place counts as
distribution of the source code, even though third parties are not
compelled to copy the source along with the object code.

  4. You may not copy, modify, sublicense, or distribute the Program
except as expressly provided under this License.  Any attempt
otherwise to copy, modify, sublicense or distribute the Program is
void, and will automatically terminate your rights under this License.
However, parties who have received copies, or rights, from you under
this License will not have their licenses terminated so long as such
parties remain in full compliance.

  5. You are not required to accept this License, since you have not
signed it.  However, nothing else grants you permission to modify or
distribute the Program or its derivative works.  These actions are
prohibited by law if you do not accept this License.  Therefore, by
modifying or distributing the Program (or any work based on the
Program), you indicate your acceptance of this License to do so, and
all its terms and conditions for copying, distributing or modifying
the Program or works based on it.

  6. Each time you redistribute the Program (or any work based on the
Program), the recipient automatically receives a license from the
original licensor to copy, distribute or modify the Program subject to
these terms and conditions.  You may not impose any further
restrictions on the recipients' exercise of the rights granted herein.
You are not responsible for enforcing compliance by third parties to
this License.

  7. If, as a consequence of a court judgment or allegation of patent
infringement or for any other reason (not limited to patent issues),
conditions are imposed on you (whether by court order, agreement or
otherwise) that contradict the conditions of this License, they do not
excuse you from the conditions of this License.  If you cannot
distribute so as to satisfy simultaneously your obligations under this
License and any other pertinent obligations, then as a consequence you
may not distribute the Program at all.  For example, if a patent
license would not permit royalty-free redistribution of the Program by
all those who receive copies directly or indirectly through you, then
the only way you could satisfy both it and this License would be to
refrain entirely from distribution of the Program.

If any portion of this section is held invalid or unenforceable under
any particular circumstance, the balance of the section is intended to
apply and the section as a whole is intended to apply in other
circumstances.

It is not the purpose of this section to induce you to infringe any
patents or other property right claims or to contest validity of any
such claims; this section has the sole purpose of protecting the
integrity of the free software distribution system, which is
implemented by public license practices.  Many people have made
generous contributions to the wide range of software distributed
through that system in reliance on consistent application of that
system; it is up to the author/donor to decide if he or she is willing
to distribute software through any other system and a licensee cannot
impose that choice.

This section is intended to make thoroughly clear what is believed to
be a consequence of the rest of this License.

  8. If the distribution and/or use of the Program is restricted in
certain countries either by patents or by copyrighted interfaces, the
original copyright holder who places the Program under this License
may add an explicit geographical distribution limitation excluding
those countries, so that distribution is permitted only in or among
countries not thus excluded.  In such case, this License incorporates
the limitation as if written in the body of this License.

  9. The Free Software Foundation may publish revised and/or new versions
of the General Public License from time to time.  Such new versions will
be similar in spirit to the present version, but may differ in detail to
address new problems or concerns.

Each version is given a distinguishing version number.  If the Program
specifies a version number of this License which applies to it and "any
later version", you have the option of following the terms and conditions
either of that version or of any later version published by the Free
Software Foundation.  If the Program does not specify a version number of
this License, you may choose any version ever published by the Free Software
Foundation.

  10. If you wish to incorporate parts of the Program into other free
programs whose distribution conditions are different, write to the author
to ask for permission.  For software which is copyrighted by the Free
Software Foundation, write to the Free Software Foundation; we sometimes
make exceptions for this.  Our decision will be guided by the two goals
of preserving the free status of all derivatives of our free software and
of promoting the sharing and reuse of software generally.

			    NO WARRANTY

  11. BECAUSE THE PROGRAM IS LICENSED FREE OF CHARGE, THERE IS NO WARRANTY
FOR THE PROGRAM, TO THE EXTENT PERMITTED BY APPLICABLE LAW.  EXCEPT WHEN
OTHERWISE STATED IN WRITING THE COPYRIGHT HOLDERS AND/OR OTHER PARTIES
PROVIDE THE PROGRAM "AS IS" WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESSED
OR IMPLIED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.  THE ENTIRE RISK AS
TO THE QUALITY AND PERFORMANCE OF THE PROGRAM IS WITH YOU.  SHOULD THE
PROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF ALL NECESSARY SERVICING,
REPAIR OR CORRECTION.

  12. IN NO EVENT UNLESS REQUIRED BY APPLICABLE LAW OR AGREED TO IN WRITING
WILL ANY COPYRIGHT HOLDER, OR ANY OTHER PARTY WHO MAY MODIFY AND/OR
REDISTRIBUTE THE PROGRAM AS PERMITTED ABOVE, BE LIABLE TO YOU FOR DAMAGES,
INCLUDING ANY GENERAL, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES ARISING
OUT OF THE USE OR INABILITY TO USE THE PROGRAM (INCLUDING BUT NOT LIMITED
TO LOSS OF DATA OR DATA BEING RENDERED INACCURATE OR LOSSES SUSTAINED BY
YOU OR THIRD PARTIES OR A FAILURE OF THE PROGRAM TO OPERATE WITH ANY OTHER
PROGRAMS), EVEN IF SUCH HOLDER OR OTHER PARTY HAS BEEN ADVISED OF THE
POSSIBILITY OF SUCH DAMAGES.

		     END OF TERMS AND CONDITIONS

	    How to Apply These Terms to Your New Programs

  If you develop a new program, and you want it to be of the greatest
possible use to the public, the best way to achieve this is to make it
free software which everyone can redistribute and change under these terms.

  To do so, attach the following notices to the program.  It is safest
to attach them to the start of each source file to most effectively
convey the exclusion of warranty; and each file should have at least
the "copyright" line and a pointer to where the full notice is found.

    <one line to give the program's name and a brief idea of what it does.>
    Copyright (C) <year>  <name of author>

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


Also add information on how to contact you by electronic and paper mail.

If the program is interactive, make it output a short notice like this
when it starts in an interactive mode:

    Gnomovision version 69, Copyright (C) year  name of author
    Gnomovision comes with ABSOLUTELY NO WARRANTY; for details type `show w'.
    This is free software, and you are welcome to redistribute it
    under certain conditions; type `show c' for details.

The hypothetical commands `show w' and `show c' should show the appropriate
parts of the General Public License.  Of course, the commands you use may
be called something other than `show w' and `show c'; they could even be
mouse-clicks or menu items--whatever suits your program.

You should also get your employer (if you work as a programmer) or your
school, if any, to sign a "copyright disclaimer" for the program, if
necessary.  Here is a sample; alter the names:

  Yoyodyne, Inc., hereby disclaims all copyright interest in the program
  `Gnomovision' (which makes passes at compilers) written by James Hacker.

  <signature of Ty Coon>, 1 April 1989
  Ty Coon, President of Vice

This General Public License does not permit incorporating your program into
proprietary programs.  If your program is a subroutine library, you may
consider it more useful to permit linking proprietary applications with the
library.  If this is what you want to do, use the GNU Library General
Public License instead of this License.
```

## Kết quả kiểm tra file handoff này

Đã khôi phục 14 source file từ chính Markdown, đối chiếu hash của tất cả file và kiểm tra cú pháp Python. Helper build đã compile/link lại backend và fixture từ các file khôi phục, dùng SDK Qt3 đã source-build trước đó. Smoke test thực tế qua window, button, input, checkbox, menu/submenu, file dialog và stale handle đã thành công.

Helper SDK mới đã được kiểm tra cú pháp và kiểm tra rằng cache thiếu sẽ dừng mà không download khi chưa có cờ cho phép. Chưa chạy lại toàn bộ SDK build từ đầu trong lần tạo handoff; kết quả hai lần source-build SDK là bằng chứng của milestone trước. Kiro phải ghi kết quả build/test riêng tại môi trường mới.

```json
{
  "restoredFiles": 14,
  "allSourceHashesMatch": true,
  "allPythonSyntaxChecked": true,
  "offlineDefaultRefusesMissingCacheWithoutDownloading": true,
  "rebuiltBackendAndFixtureFromMarkdown": true,
  "smoke": {
    "passed": true,
    "qt": "3.3.8",
    "controls": [
      "window",
      "button",
      "input",
      "checkbox",
      "menu",
      "submenu",
      "Qt3 file dialog"
    ],
    "staleHandleVerified": true
  },
  "sdkFromScratchThisTurn": false,
  "sdkNote": "Reused the previously source-built Qt3 SDK; new SDK orchestration was syntax/offline-behavior checked."
}
```
