import sqlite3
from src.storage import Storage

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
    def __setattr__(self, name, value):
        if name == 'real_conn':
            super().__setattr__(name, value)
        else:
            setattr(self.real_conn, name, value)

dummy = DummyConn(global_conn)
dummy.row_factory = sqlite3.Row
print(dummy.row_factory)
