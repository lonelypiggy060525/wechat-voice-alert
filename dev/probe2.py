import sys
import uiautomation as auto

auto.SetGlobalSearchTimeout(3)

w = auto.WindowControl(ClassName="Qt51514QWindowIcon", Name="微信")
print("exists:", w.Exists(1), "handle:", w.NativeWindowHandle, "rect:", w.BoundingRectangle)
print("type:", w.ControlTypeName, "class:", repr(w.ClassName), "pid:", w.ProcessId)
print("--- children ---")


def dump(ctrl, depth, maxdepth):
    if depth > maxdepth:
        return
    try:
        kids = ctrl.GetChildren()
    except Exception as e:
        print("  " * depth + f"<err {e}>")
        return
    for k in kids:
        try:
            print("  " * depth + f"{k.ControlTypeName} class={k.ClassName!r} name={k.Name!r} aid={k.AutomationId!r} rect={k.BoundingRectangle}")
        except Exception as e:
            print("  " * depth + f"<err {e}>")
            continue
        dump(k, depth + 1, maxdepth)


dump(w, 1, 5)
