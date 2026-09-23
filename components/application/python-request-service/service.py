"""Local reference service. SQLite is a demo adapter, not a distributed cloud queue."""
import json
import sqlite3
import uuid
from contextlib import contextmanager


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, title TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, dedupe_key TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL, status TEXT NOT NULL, result TEXT);
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_request(self, title):
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise ValueError('title must contain 1–200 characters')
        item = {'id': str(uuid.uuid4()), 'title': title.strip()}
        with self.connection() as db:
            db.execute('INSERT INTO requests VALUES (?, ?)', (item['id'], item['title']))
        return item

    def get_request(self, key):
        with self.connection() as db:
            row = db.execute('SELECT id, title FROM requests WHERE id=?', (key,)).fetchone()
        return dict(zip(('id', 'title'), row)) if row else None

    def enqueue(self, key, text):
        if not isinstance(key, str) or not 1 <= len(key) <= 128:
            raise ValueError('idempotency key must contain 1–128 characters')
        if not isinstance(text, str) or not 1 <= len(text) <= 2000:
            raise ValueError('text must contain 1–2000 characters')
        payload = json.dumps({'text': text}, sort_keys=True)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT id,payload FROM jobs WHERE dedupe_key=?', (key,)).fetchone()
            if row:
                if row[1] != payload:
                    raise Conflict('idempotency key already used with a different payload')
                return self._job(db, row[0])
            job_id = str(uuid.uuid4())
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,NULL)', (job_id, key, payload, 'queued'))
            return self._job(db, job_id)

    @staticmethod
    def _job(db, key):
        row = db.execute('SELECT id,status,result FROM jobs WHERE id=?', (key,)).fetchone()
        return dict(zip(('id', 'status', 'result'), row)) if row else None

    def get_job(self, key):
        with self.connection() as db:
            return self._job(db, key)

    def work_once(self):
        # Atomic local transform/result commit. External side effects would require an
        # outbox or provider-specific acknowledgement/retry contract, not this lock.
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT id,payload FROM jobs WHERE status='queued' ORDER BY rowid LIMIT 1").fetchone()
            if not row:
                return None
            result = json.loads(row[1])['text'].upper()
            db.execute("UPDATE jobs SET status='complete',result=? WHERE id=?", (result, row[0]))
            return self._job(db, row[0])
