"""POC-only local SQLite persistence; one transaction per user operation."""
import json
from contextlib import contextmanager
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path, seed_path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), document TEXT NOT NULL)')
            if not db.execute('SELECT 1 FROM state WHERE id=1').fetchone():
                seed = json.loads(Path(seed_path).read_text(encoding='utf-8'))
                db.execute('INSERT INTO state VALUES (1,?)', (json.dumps(seed, ensure_ascii=False),))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def read(self):
        with self.connect() as db:
            return json.loads(db.execute('SELECT document FROM state WHERE id=1').fetchone()[0])

    def change(self, operation, bump_revision=True):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            state = json.loads(db.execute('SELECT document FROM state WHERE id=1').fetchone()[0])
            result = operation(state)
            if bump_revision:
                state['revision'] += 1
            db.execute('UPDATE state SET document=? WHERE id=1', (json.dumps(state, ensure_ascii=False),))
            return state, result
