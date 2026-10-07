"""Durable local event archive; the in-memory monitor window remains bounded."""
from pathlib import Path
import logging
from contextlib import contextmanager
import sqlite3
from contracts.models import TrafficEvent
from contracts.history import EventArchivePage

logger = logging.getLogger(__name__)
class EventArchive:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.failed = False
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL, intersection_id TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS archive_intersection ON events(intersection_id,id)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=.25)
        try:
            with db:
                yield db
        finally:
            db.close()

    def append(self, event):
        try:
            with self.connect() as db:
                db.execute('INSERT OR IGNORE INTO events(event_id,intersection_id,kind,payload) VALUES(?,?,?,?)',
                    (event.event_id,event.intersection_id,event.event_type,event.model_dump_json()))
        except sqlite3.Error:
            # Archive failure must not alter lamp transitions or heartbeat timing.
            self.failed = True
            logger.exception('Event archive write failed; controller continues independently')

    def page(self, intersection, at, before=None, limit=50, event_filter='all'):
        if not 1 <= limit <= 100 or event_filter not in ('all','phase','incident') or (before is not None and before < 1):
            raise ValueError('Invalid archive page')
        if self.failed:
            raise RuntimeError('Archive persistence failed; completeness cannot be confirmed')
        where, args = ['intersection_id=?'], [intersection]
        if before is not None:
            where.append('id<?'); args.append(before)
        if event_filter == 'phase':
            where.append("kind='phase_changed'")
        elif event_filter == 'incident':
            where.append("kind IN ('fault','recovered','clearance_held','service_stopped')")
        with self.connect() as db:
            rows = db.execute('SELECT id,payload FROM events WHERE '+ ' AND '.join(where)+' ORDER BY id DESC LIMIT ?',args+[limit+1]).fetchall()
        more = len(rows)>limit
        rows = rows[:limit]
        return EventArchivePage(intersection_id=intersection, events=[TrafficEvent.model_validate_json(v) for _,v in rows],
            next_before=rows[-1][0] if more else None,has_more=more,generated_at=at,filter=event_filter)
