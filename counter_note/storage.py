import json
import sqlite3
import time
from pathlib import Path


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS matches (
                id TEXT PRIMARY KEY, patch TEXT NOT NULL, started INTEGER NOT NULL,
                platform TEXT NOT NULL, queue INTEGER NOT NULL, facts TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS matches_scope ON matches(platform, queue, patch, started);
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS skipped (id TEXT PRIMARY KEY, checked INTEGER NOT NULL);
        """)

    def close(self):
        self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def get(self, key, default=None):
        row = self.db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO metadata VALUES (?,?)", (key, json.dumps(value)))

    def seen(self, match_id):
        return bool(self.db.execute("SELECT 1 FROM matches WHERE id=? UNION ALL SELECT 1 FROM skipped WHERE id=? LIMIT 1", (match_id, match_id)).fetchone())

    def skip(self, match_id):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO skipped VALUES (?,?)", (match_id, int(time.time())))

    def add(self, match_id, patch, started, platform, queue, facts):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO matches VALUES (?,?,?,?,?,?)", (match_id, patch, started, platform, queue, json.dumps(facts, separators=(",", ":"))))

    def records(self, platform, queue, patch, since):
        for (facts,) in self.db.execute("SELECT facts FROM matches WHERE platform=? AND queue=? AND patch=? AND started>=? ORDER BY id", (platform, queue, patch, since)):
            yield from json.loads(facts)

    def count(self, platform, queue, patch, since):
        return self.db.execute("SELECT COUNT(*) FROM matches WHERE platform=? AND queue=? AND patch=? AND started>=?", (platform, queue, patch, since)).fetchone()[0]

    def prune(self, config):
        cutoff = int(time.time()) - config["retention_days"] * 86400
        with self.db:
            self.db.execute("DELETE FROM matches WHERE started<?", (cutoff,))
            self.db.execute("DELETE FROM skipped WHERE checked<?", (cutoff,))
            self.db.execute("DELETE FROM matches WHERE id IN (SELECT id FROM matches ORDER BY started DESC LIMIT -1 OFFSET ?)", (config["max_stored_matches"],))
            self.db.execute("DELETE FROM skipped WHERE id IN (SELECT id FROM skipped ORDER BY checked DESC LIMIT -1 OFFSET ?)", (config["max_stored_matches"] * 3,))

    def backup(self, path):
        target = sqlite3.connect(path)
        try:
            self.db.backup(target)
        finally:
            target.close()
