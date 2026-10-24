import json
import os
import sqlite3
import time

SCHEMA = """create table if not exists analyses (
  id integer primary key autoincrement, kind text not null, created_at text not null, title text not null,
  result text not null, run_id text, payload text not null)"""
KINDS = ("health", "upgrade")
MAX_PAYLOAD = 2_000_000


class History:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with self.connect() as connection:
            connection.execute(SCHEMA)

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def add(self, kind, title, result, payload, run_id=None):
        if kind not in KINDS:
            raise ValueError("unknown kind")
        body = json.dumps(payload, sort_keys=True)
        if len(body) > MAX_PAYLOAD:
            raise ValueError("the record is too large to store")
        with self.connect() as connection:
            cursor = connection.execute("insert into analyses (kind, created_at, title, result, run_id, payload) values (?, ?, ?, ?, ?, ?)",
                                        (kind, time.strftime("%Y-%m-%dT%H:%M:%S%z"), title[:200], result[:80], run_id, body))
            return cursor.lastrowid

    def recent(self, limit=50):
        with self.connect() as connection:
            rows = connection.execute("select id, kind, created_at, title, result, run_id from analyses order by id desc limit ?", (int(limit),)).fetchall()
        return [dict(row) for row in rows]

    def get(self, record_id):
        with self.connect() as connection:
            row = connection.execute("select * from analyses where id = ?", (int(record_id),)).fetchone()
        if not row:
            return None
        found = dict(row)
        found["payload"] = json.loads(found["payload"])
        return found

    def has_run(self, run_id):
        with self.connect() as connection:
            return connection.execute("select 1 from analyses where run_id = ?", (run_id,)).fetchone() is not None
