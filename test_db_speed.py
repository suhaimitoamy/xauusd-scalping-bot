import time
from src.storage import Storage

storage = Storage()
start = time.time()
for i in range(100):
    conn = storage.get_connection()
    conn.execute("SELECT 1")
    conn.close()
print(f"Normal: {time.time()-start:.2f}s")

original_get = Storage.get_connection
def fast_get(self):
    conn = original_get(self)
    conn.execute("PRAGMA synchronous = OFF")
    return conn
Storage.get_connection = fast_get

start = time.time()
for i in range(100):
    conn = storage.get_connection()
    conn.execute("SELECT 1")
    conn.close()
print(f"Fast: {time.time()-start:.2f}s")
