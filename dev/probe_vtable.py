"""Walk the MSAA tree via raw vtable calls (no comtypes pointer weirdness)."""
import ctypes
from ctypes import wintypes, c_ulong, c_ushort, c_ubyte

oleacc = ctypes.WinDLL("oleacc", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

VT_I4 = 3
VT_EMPTY = 0


class VARIANT(ctypes.Structure):
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort),
                ("val", ctypes.c_longlong)]


class V4(ctypes.Structure):
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort),
                ("lVal", ctypes.c_long), ("pad", ctypes.c_long)]


def mkvar(i):
    if i == 0:
        return V4(vt=VT_EMPTY)
    return V4(vt=VT_I4, lVal=i)


class IAcc:
    def __init__(self, ptr):
        self.ptr = ptr

    def _fn(self, idx, proto):
        vtbl = ctypes.cast(self.ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        return ctypes.WINFUNCTYPE(*proto)(vtbl[idx])

    def count(self):
        n = ctypes.c_long(0)
        fn = self._fn(8, (ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_long)))
        fn(self.ptr, ctypes.byref(n))
        return n.value

    def name(self, child=0):
        bstr = ctypes.c_void_p()
        fn = self._fn(10, (ctypes.HRESULT, ctypes.c_void_p, V4, ctypes.POINTER(ctypes.c_void_p)))
        fn(self.ptr, mkvar(child), ctypes.byref(bstr))
        if not bstr.value:
            return ""
        s = ctypes.wstring_at(bstr.value)
        ctypes.WinDLL("oleaut32").SysFreeString(bstr)
        return s

    def role(self, child=0):
        v = V4()
        fn = self._fn(13, (ctypes.HRESULT, ctypes.c_void_p, V4, ctypes.POINTER(V4)))
        fn(self.ptr, mkvar(child), ctypes.byref(v))
        return v.lVal


hwnd = 329612
ptr = ctypes.c_void_p()
IID = ctypes.c_byte * 16
# IID_IAccessible {618736E0-3C3D-11CF-810C-00AA00389B71}
from ctypes import c_ubyte
class GUID(ctypes.Structure):
    _fields_ = [("d1", c_ulong), ("d2", c_ushort), ("d3", c_ushort), ("d4", c_ubyte * 8)]


iid = GUID(0x618736E0, 0x3C3D, 0x11CF, (c_ubyte * 8)(0x81, 0x0C, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71))
hr = oleacc.AccessibleObjectFromWindow(wintypes.HWND(hwnd), ctypes.c_ulong(0xFFFFFFFC), ctypes.byref(iid), ctypes.byref(ptr))
print("hr", hr, "ptr", ptr.value)
acc = IAcc(ptr.value)
print("childCount", acc.count())
print("root name", repr(acc.name(0)), "role", acc.role(0))
n = acc.count()
for i in range(1, min(n, 40) + 1):
    print(i, repr(acc.name(i)), acc.role(i))
