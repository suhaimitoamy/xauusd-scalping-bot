import sqlite3
from src.storage import Storage

storage = Storage()
global_conn = sqlite3.connect('data/xauusd_bot.sqlite')

class DummyConn:
    def __init__(self, real_conn):
        self.real_conn = real_conn
    def close(self):
        pass
    def commit(self):
        pass # don't commit
    def __getattr__(self, name):
        return getattr(self.real_conn, name)

def fast_get(self):
    return DummyConn(global_conn)

Storage.get_connection = fast_get

import time
start = time.time()
for i in range(100):
    conn = storage.get_connection()
    conn.execute("SELECT 1")
    conn.close()
print(f"Wrapper: {time.time()-start:.4f}s")
