import sys
import uiautomation as auto

auto.SetGlobalSearchTimeout(2)

root = auto.GetRootControl()
print("=== top-level windows ===")
for w in root.GetChildren():
    try:
        pid = w.ProcessId
        name = w.Name
        cls = w.ClassName
    except Exception as e:
        print("err", e)
        continue
    print(f"pid={pid} type={w.ControlTypeName} class={cls!r} name={name!r} rect={w.BoundingRectangle}")
