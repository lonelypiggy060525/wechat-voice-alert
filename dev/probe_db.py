import sqlite3, os, re

db = os.path.join(os.environ["TMPDIR"], "wpndb.db")
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
cur = con.cursor()
tables = [r[0] for r in cur.execute("select name from sqlite_master where type='table'")]
print("tables:", tables)
for t in ("Notification", "Handler"):
    if t in tables:
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
        print(f"\n{t} cols:", cols)

print("\n=== handlers ===")
try:
    for r in cur.execute("select * from Handler"):
        print(r)
except Exception as e:
    print("err", e)

print("\n=== notifications (app payload search) ===")
try:
    rows = cur.execute("select Id, HandlerId, Payload from Notification order by Id desc limit 40").fetchall()
    for rid, hid, payload in rows:
        p = payload.decode("utf-8", "replace") if isinstance(payload, (bytes, bytearray)) else str(payload)
        if re.search(r"微信|WeChat|Weixin|wechat", p, re.I) or hid in ("Tencent.WeChat", "WeChat"):
            print(f"--- id={rid} handler={hid}\n{p[:1500]}\n")
    print("total notifications:", cur.execute("select count(*) from Notification").fetchone()[0])
except Exception as e:
    print("err", e)
