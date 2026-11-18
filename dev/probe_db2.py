import sqlite3, os

db = os.path.join(os.environ["TMPDIR"], "wpndb.db")
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
cur = con.cursor()
print("=== NotificationHandler cols ===")
print([r[1] for r in cur.execute("PRAGMA table_info(NotificationHandler)")])
print("=== handlers ===")
for r in cur.execute("select * from NotificationHandler limit 30"):
    print(r)
print("=== notifications ===")
for r in cur.execute("select Id, HandlerId, Type, substr(Payload,1,400) from Notification"):
    print(r)
