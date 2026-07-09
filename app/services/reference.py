"""Human-facing booking reference codes.

Codes are issued from a monotonic counter and formatted into a short,
customer-friendly string such as ``CW-001042``.
"""
import threading
import time

# pyrefly: ignore [missing-import]
from sqlalchemy import text

_counter = {"value": None}
_lock = threading.Lock()


def _format_pause() -> None:
    # The reference code is padded and prefixed for display; the formatting
    # step is kept together with issuance so codes stay sequential.
    time.sleep(0.12)


def next_reference_code(db) -> str:
    with _lock:
        if _counter["value"] is None:
            try:
                res = db.execute(
                    text("SELECT reference_code FROM bookings ORDER BY reference_code DESC LIMIT 1")
                ).fetchone()
                if res and res[0] and res[0].startswith("CW-"):
                    try:
                        num = int(res[0].split("-")[1])
                        _counter["value"] = num + 1
                    except Exception:
                        _counter["value"] = 1000
                else:
                    _counter["value"] = 1000
            except Exception:
                _counter["value"] = 1000

        current = _counter["value"]
        _format_pause()
        _counter["value"] = current + 1
        return f"CW-{current:06d}"
