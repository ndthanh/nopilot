"""Read candidate COM pointers externally; never scan target pages from inside Teams."""
import ctypes as C
from ctypes import wintypes as W
import struct
import time

class MemoryInfo(C.Structure):
    _fields_=[('BaseAddress',C.c_void_p),('AllocationBase',C.c_void_p),
              ('AllocationProtect',W.DWORD),('PartitionId',W.WORD),
              ('RegionSize',C.c_size_t),('State',W.DWORD),('Protect',W.DWORD),('Type',W.DWORD)]

def discover_frames(pid,vtable):
    """Windows VM_READ only. Skip guard/noaccess pages and changing mappings."""
    kernel=C.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
    kernel.CloseHandle.argtypes=[W.HANDLE]
    kernel.VirtualQueryEx.argtypes=[W.HANDLE,C.c_void_p,C.POINTER(MemoryInfo),C.c_size_t]
    kernel.VirtualQueryEx.restype=C.c_size_t
    kernel.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]
    kernel.ReadProcessMemory.restype=W.BOOL
    handle=kernel.OpenProcess(0x400|0x10,False,pid)
    if not handle:raise C.WinError(C.get_last_error())
    pattern=struct.pack('<Q',vtable)
    address=0;frames=set();scanned=0;skipped=0;failed=0
    size=256*1024;buffer=C.create_string_buffer(size)
    started=time.monotonic()
    try:
        while address<0x7FFFFFFFFFFF:
            info=MemoryInfo()
            if not kernel.VirtualQueryEx(handle,C.c_void_p(address),C.byref(info),C.sizeof(info)):break
            base=info.BaseAddress or 0
            end=base+info.RegionSize
            if end<=address:break
            # COM objects live in committed private writable mappings. In particular,
            # do not touch PAGE_GUARD, including thread stack guard pages.
            readable=info.State==0x1000 and info.Type==0x20000 and not (info.Protect & 0x100) and (info.Protect & 0xFF) in (0x04,0x08,0x40,0x80)
            if readable and info.RegionSize<=128*1024*1024:
                cursor=base
                while cursor<end:
                    amount=min(size,end-cursor);read=C.c_size_t()
                    ok=kernel.ReadProcessMemory(handle,C.c_void_p(cursor),buffer,amount,C.byref(read))
                    if ok:
                        data=buffer.raw[:read.value];scanned+=read.value;offset=0
                        while True:
                            offset=data.find(pattern,offset)
                            if offset<0:break
                            hit=cursor+offset
                            if hit%8==0:frames.add(hit)
                            offset+=1
                        if len(frames)>64:raise RuntimeError('Too many frame pointer candidates; refusing native calls')
                    else:failed+=amount
                    cursor+=amount if amount<8 else amount-7
            elif readable:skipped+=info.RegionSize
            address=end
    finally:kernel.CloseHandle(handle)
    return {'frames':[hex(p) for p in sorted(frames)],'scannedBytes':scanned,
            'skippedBytes':skipped,'failedReadBytes':failed,'elapsedSeconds':round(time.monotonic()-started,3),
            'method':'external VirtualQueryEx + ReadProcessMemory; guard pages excluded'}
