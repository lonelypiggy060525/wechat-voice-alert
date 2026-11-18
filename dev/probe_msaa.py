"""Probe MSAA (IAccessible) tree of the WeChat main window - Qt apps often expose this."""
import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
oleacc = ctypes.WinDLL("oleacc", use_last_error=True)

hwnd = 329612
print("IsWindow:", bool(user32.IsWindow(hwnd)))
print("IsWindowVisible:", bool(user32.IsWindowVisible(hwnd)))

# Use raw IAccessible vtable via ctypes: simplest is AccessibleObjectFromWindow then
# use the IAccessible dispatch interface through oleacc's AccessibleChildren.
from comtypes.client import GetModule
GetModule(r"C:\Windows\System32\oleacc.dll")
from comtypes.gen.Accessibility import IAccessible

p = ctypes.POINTER(IAccessible)()
hr = oleacc.AccessibleObjectFromWindow(
    wintypes.HWND(hwnd), ctypes.c_ulong(0xFFFFFFFC),  # OBJID_CLIENT
    ctypes.byref(IAccessible._iid_), ctypes.byref(p))
print("AccessibleObjectFromWindow hr=", hr)
if hr == 0 and p:
    try:
        acc = p[0]
    except Exception:
        acc = ctypes.cast(p, ctypes.POINTER(IAccessible)).contents
    print("child count:", acc.accChildCount)
    print("name:", repr(acc.accName(0)))
    print("role:", acc.accRole(0))
    print("state:", acc.accState(0))
    kids = []
    for i in range(1, min(acc.accChildCount, 60) + 1):
        try:
            name = acc.accName(i)
            role = acc.accRole(i)
            desc = acc.accDescription(i)
            kids.append((i, role, name, desc))
        except Exception as e:
            kids.append((i, "err", str(e), ""))
    for k in kids[:60]:
        print(k)
