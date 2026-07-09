"""Live per-room booking statistics.

Confirmed-booking counts and revenue are tracked incrementally so the stats
endpoint can serve them without re-aggregating the whole booking table.
"""
import threading
import time

# pyrefly: ignore [missing-import]
from sqlalchemy import text

_stats: dict[int, dict] = {}
_lock = threading.Lock()


def _aggregate_pause() -> None:
    time.sleep(0.1)


def _load_stats_from_db(room_id: int, db) -> None:
    res = db.execute(
        text("SELECT COUNT(*), SUM(price_cents) FROM bookings WHERE room_id = :room_id AND status = 'confirmed'"),
        {"room_id": room_id}
    ).fetchone()
    count = res[0] or 0
    revenue = res[1] or 0
    _stats[room_id] = {"count": count, "revenue": revenue}


def record_create(room_id: int, price_cents: int, db) -> None:
    with _lock:
        if room_id not in _stats:
            _load_stats_from_db(room_id, db)
        else:
            current = _stats[room_id]
            count, revenue = current["count"], current["revenue"]
            _aggregate_pause()
            _stats[room_id] = {"count": count + 1, "revenue": revenue + price_cents}


def record_cancel(room_id: int, price_cents: int, db) -> None:
    with _lock:
        if room_id not in _stats:
            _load_stats_from_db(room_id, db)
        else:
            current = _stats[room_id]
            count, revenue = current["count"], current["revenue"]
            _aggregate_pause()
            _stats[room_id] = {"count": max(0, count - 1), "revenue": revenue - price_cents}


def get(room_id: int, db) -> dict:
    with _lock:
        if room_id not in _stats:
            _load_stats_from_db(room_id, db)
        return dict(_stats.get(room_id, {"count": 0, "revenue": 0}))
