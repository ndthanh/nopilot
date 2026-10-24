"""Regenerate the WebView2 manifest using Microsoft's matching public PDB."""
import argparse
import ctypes as C
import ctypes.wintypes as W
import hashlib
import json
import pathlib
import shutil
import struct
import urllib.request
import uuid
import frida
import pefile
from bridge import HERE, teams_pid

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pid',type=int)
    parser.add_argument('--cache-dir',type=pathlib.Path,default=pathlib.Path('work/teams-frida-symbols'))
    args=parser.parse_args()
    session=frida.attach(args.pid or teams_pid())
    try:
        probe=session.create_script("rpc.exports.path=()=>Process.getModuleByName('EmbeddedBrowserWebView.dll').path")
        probe.load()
        module=pathlib.Path(probe.exports_sync.path())
    finally:
        session.detach()
    image=pefile.PE(str(module))
    if image.FILE_HEADER.Machine!=0x8664:
        raise RuntimeError('This PoC supports x64 only')
    codeview=next(image.get_data(d.struct.AddressOfRawData,d.struct.SizeOfData) for d in image.DIRECTORY_ENTRY_DEBUG if d.struct.Type==2)
    if not codeview.startswith(b'RSDS'):raise RuntimeError('Unsupported PDB format')
    name=pathlib.PureWindowsPath(codeview[24:].rstrip(b'\0').decode()).name
    key=uuid.UUID(bytes_le=codeview[4:20]).hex.upper()+format(struct.unpack_from('<I',codeview,20)[0],'X')
    cache=args.cache_dir.resolve()/key
    cache.mkdir(parents=True,exist_ok=True)
    pdb=cache/name
    url=f'https://msdl.microsoft.com/download/symbols/{name}/{key}/{name}'
    if not pdb.exists():
        print('Downloading matching public symbols:',url,flush=True)
        temp=pdb.with_suffix('.partial')
        with urllib.request.urlopen(url,timeout=60) as response,temp.open('wb') as out:
            shutil.copyfileobj(response,out)
        temp.replace(pdb)
    dbg=C.WinDLL('dbghelp');kernel=C.WinDLL('kernel32')
    kernel.GetCurrentProcess.restype=W.HANDLE
    handle=kernel.GetCurrentProcess()
    dbg.SymInitializeW.argtypes=[W.HANDLE,W.LPCWSTR,W.BOOL];dbg.SymInitializeW.restype=W.BOOL
    dbg.SymSetOptions(0x10|0x4|0x200)
    if not dbg.SymInitializeW(handle,str(cache),False):raise C.WinError()
    dbg.SymLoadModuleExW.argtypes=[W.HANDLE,W.HANDLE,W.LPCWSTR,W.LPCWSTR,C.c_uint64,W.DWORD,C.c_void_p,W.DWORD]
    dbg.SymLoadModuleExW.restype=C.c_uint64
    base=dbg.SymLoadModuleExW(handle,None,str(pdb),None,0x10000000,image.OPTIONAL_HEADER.SizeOfImage,None,0)
    if not base:raise C.WinError()
    class Symbol(C.Structure):
        _fields_=[('SizeOfStruct',W.ULONG),('TypeIndex',W.ULONG),('Reserved',C.c_uint64*2),('Index',W.ULONG),('Size',W.ULONG),('ModBase',C.c_uint64),('Flags',W.ULONG),('Value',C.c_uint64),('Address',C.c_uint64),('Register',W.ULONG),('Scope',W.ULONG),('Tag',W.ULONG),('NameLen',W.ULONG),('MaxNameLen',W.ULONG),('Name',C.c_char*1)]
    Callback=C.WINFUNCTYPE(W.BOOL,C.POINTER(Symbol),W.ULONG,C.c_void_p)
    found={}
    @Callback
    def collect(p,size,ctx):
        symbol=p.contents
        name=C.string_at(C.addressof(symbol)+Symbol.Name.offset,symbol.NameLen).decode(errors='replace')
        if name.startswith('??_7EmbeddedBrowserWebViewFrame@embedded_browser_webview_current') and 'ChainInterfaces' in name:
            found.setdefault('frameVtable',[]).append(symbol.Address-base)
        if name.startswith('?ExecuteScript@EmbeddedBrowserWebViewFrame@embedded_browser_webview_current'):
            found.setdefault('frameExecute',[]).append(symbol.Address-base)
        if name.startswith('?ExecuteScript@EmbeddedBrowserWebView@embedded_browser_webview_current'):
            found.setdefault('coreExecute',[]).append(symbol.Address-base)
        if name.startswith('?get_Source@EmbeddedBrowserWebView@embedded_browser_webview_current'):
            found.setdefault('coreSource',[]).append(symbol.Address-base)
        return True
    dbg.SymEnumSymbols.argtypes=[W.HANDLE,C.c_uint64,C.c_char_p,Callback,C.c_void_p];dbg.SymEnumSymbols.restype=W.BOOL
    if not dbg.SymEnumSymbols(handle,base,b'*',collect,None):raise C.WinError()
    if any(len(found.get(k,[]))!=1 for k in ['frameVtable','frameExecute','coreExecute','coreSource']):raise RuntimeError(f'Symbols are missing or ambiguous: {found}')
    config={k:v[0] for k,v in found.items()}
    pattern=struct.pack('<Q',image.OPTIONAL_HEADER.ImageBase+config.pop('coreSource'))
    tables=[]
    for section in image.sections:
        data=section.get_data();start=0
        while True:
            index=data.find(pattern,start)
            if index<0:break
            vtable=section.VirtualAddress+index-32
            if struct.unpack('<Q',image.get_data(vtable+29*8,8))[0]==image.OPTIONAL_HEADER.ImageBase+config['coreExecute']:
                tables.append(vtable)
            start=index+1
    if len(tables)!=1:raise RuntimeError(f'Teams shell vtable is missing or ambiguous: {tables}')
    config['coreVtable']=tables[0]
    config.update(moduleSha256=hashlib.sha256(module.read_bytes()).hexdigest(),architecture='x64',runtimeVersion=module.parents[2].name,symbolServer='https://msdl.microsoft.com/download/symbols/',pdb=[name,key])
    target=HERE/'build.json'
    target.write_text(json.dumps(config,indent=2),encoding='utf-8')
    print('Saved',target)
    print(json.dumps(config,indent=2))

if __name__=='__main__':main()
