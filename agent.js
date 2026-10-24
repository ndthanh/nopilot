'use strict';
// Native offsets are supplied by the validated build manifest, never guessed.
const cfg = __CONFIG__;
const module = Process.getModuleByName('EmbeddedBrowserWebView.dll');
const user32 = Process.getModuleByName('user32.dll');
const retained = [];
const liveReferences = [];
let active = 0;
let uiThread = null;

function findUiThread() {
  const getOwner = new NativeFunction(user32.getExportByName('GetWindowThreadProcessId'), 'uint', ['pointer', 'pointer']);
  const visible = new NativeFunction(user32.getExportByName('IsWindowVisible'), 'bool', ['pointer']);
  const tids = [];
  const callback = new NativeCallback(hwnd => {
    const pid = Memory.alloc(4);
    const tid = getOwner(hwnd, pid);
    if (pid.readU32() === Process.id && visible(hwnd) && !tids.includes(tid)) tids.push(tid);
    return 1;
  }, 'bool', ['pointer', 'pointer']);
  new NativeFunction(user32.getExportByName('EnumWindows'), 'bool', ['pointer', 'pointer'])(callback, NULL);
  if (tids.length !== 1) throw new Error('Expected one visible Teams UI thread; found ' + JSON.stringify(tids));
  return tids[0];
}

function onUiThread(operation, timeoutMs = 12000) {
  return new Promise((resolve, reject) => {
    let started = false, settled = false;
    const hooks = [];
    const timer = setTimeout(() => finish(new Error('UI operation timed out; reconnect before retrying a write')), timeoutMs);
    function finish(error, value) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      setImmediate(() => {
        hooks.forEach(h => h.detach());
        error ? reject(error) : resolve(value);
      });
    }
    function run() {
      if (started || settled || Process.getCurrentThreadId() !== uiThread) return;
      started = true;
      try { operation((value) => finish(null, value), (error) => finish(error)); }
      catch (error) { finish(error); }
    }
    for (const name of ['PeekMessageW', 'GetMessageW', 'DispatchMessageW']) {
      hooks.push(Interceptor.attach(user32.getExportByName(name), {onEnter: run}));
    }
    const posted = new NativeFunction(user32.getExportByName('PostThreadMessageW'), 'bool', ['uint', 'uint', 'pointer', 'pointer'])(uiThread, 0, NULL, NULL);
    if (!posted) finish(new Error('Cannot wake Teams UI thread'));
  });
}

rpc.exports = {
  metadata() {
    uiThread = findUiThread();
    const vtable = module.base.add(cfg.frameVtable);
    if (!vtable.add(19 * 8).readPointer().equals(module.base.add(cfg.frameExecute))) throw new Error('Frame vtable mismatch');
    return {pid: Process.id, uiThread, modulePath: module.path, moduleBase: module.base.toString(), moduleSize: module.size};
  },
  evaluate(address, expression, kind = 'frame') {
    if (!uiThread) uiThread = findUiThread();
    if (active) throw new Error('Only one evaluation may run at a time');
    if (retained.length > 20000) throw new Error('Reconnect to release completed callback storage');
    const frame = ptr(address);
    const vtable = kind === 'core' ? cfg.coreVtable : cfg.frameVtable;
    const functionRva = kind === 'core' ? cfg.coreExecute : cfg.frameExecute;
    if (!frame.readPointer().equals(module.base.add(vtable))) throw new Error('WebView object has changed; rediscover');
    const execute = new NativeFunction(module.base.add(functionRva), 'int', ['pointer', 'pointer', 'pointer']);
    return onUiThread((resolve, reject) => {
      if (kind === 'frame') {
        const outDestroyed = Memory.alloc(4);
        const isDestroyed = new NativeFunction(frame.readPointer().add(9 * 8).readPointer(), 'int', ['pointer', 'pointer']);
        const destroyedHR = isDestroyed(frame, outDestroyed);
        if (destroyedHR !== 0 || outDestroyed.readU32()) throw new Error('Frame is destroyed or inaccessible');
      }
      active++;
      const table = Memory.alloc(32), object = Memory.alloc(8);
      object.writePointer(table);
      let refs = 1;
      liveReferences.push(() => refs);
      const iidUnknown = '0000000000000000c000000000000046';
      const iidHandler = '7211514967ccca4b9923137112f4c4cc';
      const callbacks = [
        new NativeCallback((self, iid, out) => {
          const hex = Array.from(new Uint8Array(iid.readByteArray(16))).map(n => n.toString(16).padStart(2, '0')).join('');
          if (hex !== iidUnknown && hex !== iidHandler) { out.writePointer(NULL); return -2147467262; }
          refs++; out.writePointer(self); return 0;
        }, 'int', ['pointer', 'pointer', 'pointer']),
        new NativeCallback(() => ++refs, 'uint', ['pointer']),
        new NativeCallback(() => refs = Math.max(0, refs - 1), 'uint', ['pointer']),
        new NativeCallback((self, hr, result) => {
          active--;
          if (hr !== 0) reject(new Error('ExecuteScript callback HRESULT ' + hr));
          else {
            const raw = result.isNull() ? 'null' : result.readUtf16String();
            try { resolve(JSON.parse(raw)); } catch (_) { resolve(raw); }
          }
          return 0;
        }, 'int', ['pointer', 'int', 'pointer'])
      ];
      callbacks.forEach((callback, i) => table.add(i * 8).writePointer(callback));
      // Keep callback memory alive until session shutdown, including late callbacks.
      const script = Memory.allocUtf16String(expression);
      retained.push(table, object, script, ...callbacks);
      const hr = execute(frame, script, object);
      refs--;
      if (hr !== 0) { active--; reject(new Error('ExecuteScript HRESULT ' + hr)); }
    });
  },
  pending() { return active + liveReferences.reduce((sum, read) => sum + read(), 0); }
};
