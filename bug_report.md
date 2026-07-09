# Finalized Bug Report - CoWork REST API

This document details all 21 bugs identified, analyzed, and successfully resolved in the CoWork REST API. For each bug, the report covers the exact location, failure analysis, and side-by-side comparison of the code before and after the fix.

---

## Authentication & Token Management

### Bug 1: Access Token Lifetime Expiry
* **File & Lines**: [app/auth.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/auth.py#L50)
* **Description**: The access token's lifetime was incorrectly computed by multiplying by `60` inside the `timedelta` constructor, converting 15 minutes to 900 minutes (15 hours) instead of 900 seconds.
* **Code Change**:
  ```python
  # BEFORE
  lifetime = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
  
  # AFTER
  lifetime = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
  ```

---

### Bug 2: Logout Access Token Revocation Comparison
* **File & Lines**: [app/auth.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/auth.py#L97-L109)
* **Description**: Logging out added the access token's `jti` to `_revoked_tokens`. However, the validation check inside `get_token_payload` checked if the user ID (`sub`) was in `_revoked_tokens`, rendering the token revocation check completely ineffective.
* **Code Change**:
  ```python
  # BEFORE
  if payload.get("sub") in _revoked_tokens:
      raise AppError(401, "UNAUTHORIZED", "Token has been revoked")
  
  # AFTER
  if is_token_revoked(payload): # checks if payload.get("jti") is in _revoked_tokens
      raise AppError(401, "UNAUTHORIZED", "Token has been revoked")
  ```

---

### Bug 3: Duplicate Registration Returns Existing User
* **File & Lines**: [app/routers/auth.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/auth.py#L32-L43)
* **Description**: Registering an existing username inside the same organization returned the existing user details with status `201 Created` instead of raising a conflict error.
* **Code Change**:
  ```python
  # BEFORE
  existing = db.query(User).filter(User.org_id == org.id, User.username == payload.username).first()
  if existing is not None:
      return serialize_user(existing)
  
  # AFTER
  existing = db.query(User).filter(User.org_id == org.id, User.username == payload.username).first()
  if existing is not None:
      raise AppError(409, "USERNAME_TAKEN", "Username already taken within organization")
  ```

---

### Bug 4: Infinite Reusability of Refresh Tokens
* **File & Lines**: [app/routers/auth.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/auth.py#L89-L105) & [app/auth.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/auth.py#L92-L100)
* **Description**: Refresh tokens could be used indefinitely to create new access tokens because their `jti` values were never stored or validated for single-use rotation.
* **Code Change**:
  ```python
  # BEFORE
  @router.post("/refresh")
  def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
      data = decode_token(payload.refresh_token)
      if data.get("type") != "refresh":
          raise AppError(401, "UNAUTHORIZED", "Wrong token type")
      user = db.query(User).filter(User.id == int(data["sub"])).first()
      return { ... }
  
  # AFTER
  @router.post("/refresh")
  def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
      data = decode_token(payload.refresh_token)
      if data.get("type") != "refresh":
          raise AppError(401, "UNAUTHORIZED", "Wrong token type")
      jti = data.get("jti")
      if jti is None:
          raise AppError(401, "UNAUTHORIZED", "Refresh token has been used")
      user = db.query(User).filter(User.id == int(data["sub"])).first()
      if user is None:
          raise AppError(401, "UNAUTHORIZED", "Unknown user")
      check_and_revoke_jti(jti) # Thread-safe check-then-revoke
      return { ... }
  ```

---

## Booking Logic & Constraints

### Bug 5: Future Booking Past Start Time Grace Window
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L93)
* **Description**: The future check allowed bookings up to 5 minutes in the past due to `start <= now - timedelta(seconds=300)`.
* **Code Change**:
  ```python
  # BEFORE
  if start <= now - timedelta(seconds=300):
      raise AppError(400, "INVALID_BOOKING_WINDOW", "start_time must be in the future")
  
  # AFTER
  if start <= now:
      raise AppError(400, "INVALID_BOOKING_WINDOW", "start_time must be in the future")
  ```

---

### Bug 6: Booking Details Endpoint Overwriting Start Time
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L182)
* **Description**: The GET `/bookings/{id}` detail route overwrote the booking's `start_time` with the creation time `iso_utc(booking.created_at)`.
* **Code Change**:
  ```diff
  # BEFORE
  response = serialize_booking(booking)
  response["start_time"] = iso_utc(booking.created_at)

  # AFTER
  response = serialize_booking(booking)
```

---

### Bug 7: Timezone Offset Stripped instead of Converted
* **File & Lines**: [app/timeutils.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/timeutils.py#L10-L15)
* **Description**: The helper `parse_input_datetime` stripped timezone offsets using `.replace(tzinfo=None)` without converting them to UTC first, storing local wall-clock times as naive UTC.
* **Code Change**:
  ```python
  # BEFORE
  dt = datetime.fromisoformat(value)
  if dt.tzinfo is not None:
      dt = dt.replace(tzinfo=None)
  
  # AFTER
  dt = datetime.fromisoformat(value)
  if dt.tzinfo is not None:
      dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
  ```

---

### Bug 8: Missing Booking Minimum Duration Bounds
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L100)
* **Description**: The booking creation logic only validated the maximum duration (8 hours), allowing bookings with zero-hour or negative durations.
* **Code Change**:
  ```python
  # BEFORE
  if duration_hours > MAX_DURATION_HOURS:
      raise AppError(400, "INVALID_BOOKING_WINDOW", "duration out of range")
  
  # AFTER
  if duration_hours < MIN_DURATION_HOURS or duration_hours > MAX_DURATION_HOURS:
      raise AppError(400, "INVALID_BOOKING_WINDOW", "duration out of range")
  ```

---

### Bug 9: Overlapping Booking Operator Logic
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L57)
* **Description**: Overlap checking in `_has_conflict` used inclusive `<=` comparison, preventing back-to-back room bookings.
* **Code Change**:
  ```python
  # BEFORE
  if b.start_time <= end and start <= b.end_time:
      return True
  
  # AFTER
  if b.start_time < end and start < b.end_time:
      return True
  ```

---

### Bug 10: Bookings Pagination and Ordering Broken
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L145-L151)
* **Description**: Bookings were sorted descending instead of ascending, offset skipped page 1 due to `page * limit`, and the page limit was hardcoded to `10` ignoring user inputs.
* **Code Change**:
  ```python
  # BEFORE
  items = (
      base.order_by(Booking.start_time.desc(), Booking.id.asc())
      .offset(page * limit)
      .limit(10)
      .all()
  )
  
  # AFTER
  items = (
      base.order_by(Booking.start_time.asc(), Booking.id.asc())
      .offset((page - 1) * limit)
      .limit(limit)
      .all()
  )
  ```

---

### Bug 11: Cross-User Booking Leak
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L173-L177)
* **Description**: Non-admin users could read other members' bookings by knowing their booking IDs, as detail checks were only scoped by organization.
* **Code Change**:
  ```python
  # BEFORE
  if booking is None:
      raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found")
  
  # AFTER
  if booking is None:
      raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found")
  if user.role != "admin" and booking.user_id != user.id:
      raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found")
  ```

---

## Cancellation & CSV Export

### Bug 12: Cancellation Refund Tier Boundaries
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L210-L218)
* **Description**: A booking cancelled at exactly 48 hours notice fell into the 50% refund tier, and notice under 24 hours defaulted to 50% instead of 0%.
* **Code Change**:
  ```python
  # BEFORE
  if notice > timedelta(hours=48):
      refund_percent = 100
  else:
      refund_percent = 50
  
  # AFTER
  if notice >= timedelta(hours=48):
      refund_percent = 100
  elif notice >= timedelta(hours=24):
      refund_percent = 50
  else:
      refund_percent = 0
  ```

---

### Bug 13: Refund Amount Rounding and Ledger Mismatch
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L220-L224)
* **Description**: Cancel responses used round-to-even `round()` while `log_refund` used floating-point truncation, causing mismatches between the returned response and the database ledger.
* **Code Change**:
  ```python
  # BEFORE
  refund_amount_cents = int(round(booking.price_cents * refund_percent / 100))
  log_refund(db, booking, refund_amount_cents)
  
  # AFTER
  refund_amount_cents = int(
      (Decimal(booking.price_cents) * refund_percent / Decimal(100))
      .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
  )
  log_refund(db, booking, refund_amount_cents)
  ```

---

### Bug 14: CSV Export Cross-Org Data Leak
* **File & Lines**: [app/routers/admin.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/admin.py#L72-L75) & [app/services/export.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/services/export.py#L38-L55)
* **Description**: The export endpoint did not verify if the requested `room_id` belonged to the caller's organization under `include_all=True`, permitting data leaks across organizations.
* **Code Change**:
  ```python
  # BEFORE
  # (No check in admin.py for room ownership)
  csv_body = generate_export(db, admin.org_id, admin.id, room_id, include_all)
  
  # AFTER
  if room_id is not None:
      room = db.query(Room).filter(Room.id == room_id, Room.org_id == admin.org_id).first()
      if room is None:
          raise AppError(404, "ROOM_NOT_FOUND", "Room not found")
  csv_body = generate_export(db, admin.org_id, admin.id, room_id, include_all)
  ```

---

### Bug 15: Missing Cache Invalidation Gaps
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L126-L127), [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L228-L229), & [app/routers/rooms.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/rooms.py#L57)
* **Description**: Reports remained stale because booking creation did not invalidate report caches, cancellations did not invalidate availability caches, and room creations did not invalidate reports.
* **Code Change**:
  Added missing cache invalidation calls upon room/booking creations and cancellations:
  * `cache.invalidate_report(org_id)` on booking creation, cancellation, and room creation.
  * `cache.invalidate_availability(room_id, date)` on booking creation and cancellation.

---

## Concurrency & Race Conditions

### Bug 16: Lock-Ordering Deadlock in Notifications
* **File & Lines**: [app/services/notifications.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/services/notifications.py#L24-L36)
* **Description**: `notify_created` acquired locks `_email` -> `_audit`, whereas `notify_cancelled` acquired them in reverse order (`_audit` -> `_email`), leading to concurrent deadlocks.
* **Code Change**:
  ```python
  # BEFORE (notify_cancelled)
  with _audit_lock:
      _write_audit("cancelled", booking)
      with _email_lock:
          _send_email("cancelled", booking)
  
  # AFTER (notify_cancelled - synchronized order)
  with _email_lock:
      _send_email("cancelled", booking)
      with _audit_lock:
          _write_audit("cancelled", booking)
  ```

---

### Bug 17: Concurrent Booking Double Creation and Quotas
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L107-L114)
* **Description**: Concurrent booking requests could bypass conflict/quota constraints due to thread yields inside `time.sleep` calls, resulting in double bookings.
* **Code Change**:
  ```python
  # BEFORE
  # (no lock wrapping conflict checking and database commit)
  
  # AFTER
  with _booking_write_lock:
      db.rollback()  # Clears cached snapshot to read latest committed state
      if _has_conflict(db, room.id, start, end):
          raise AppError(409, "ROOM_CONFLICT", "...")
  ```

---

### Bug 18: Concurrent Cancellations and Double Refunds
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L200-L208)
* **Description**: Simultaneous cancellation requests could bypass status verification and commit multiple refund logs due to database snapshot caching.
* **Code Change**:
  ```python
  # BEFORE
  # (no lock wrapping status checking and cancel commit)
  
  # AFTER
  with _booking_write_lock:
      db.rollback()
      booking = db.query(Booking)...first()
      if booking.status == "cancelled":
          raise AppError(409, "ALREADY_CANCELLED", "...")
  ```

---

### Bug 19: Sequence Counter Race in Reference Code Generation
* **File & Lines**: [app/services/reference.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/services/reference.py#L20-L24)
* **Description**: Concurrent booking creations could read identical counter states before increments, generating duplicate reference codes.
* **Code Change**:
  ```python
  # BEFORE
  current = _counter["value"]
  _format_pause()
  _counter["value"] = current + 1
  return f"CW-{current:06d}"
  
  # AFTER
  with _lock:
      # lazy init from DB if needed
      current = _counter["value"]
      _format_pause()
      _counter["value"] = current + 1
      return f"CW-{current:06d}"
  ```

---

### Bug 20: Rate Limit Verification Race Condition
* **File & Lines**: [app/services/ratelimit.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/services/ratelimit.py#L18-L26)
* **Description**: Concurrent request arrivals read identical stale timestamp buckets, bypassing rolling-window request limits.
* **Code Change**:
  ```python
  # BEFORE
  bucket = _buckets.get(user_id, [])
  # ...
  _buckets[user_id] = bucket
  
  # AFTER
  with _lock:
      bucket = _buckets.get(user_id, [])
      # ...
      _buckets[user_id] = bucket
  ```

---

### Bug 21: Lost Incremental Statistics Updates & Lazy Initialization
* **File & Lines**: [app/services/stats.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/services/stats.py#L30-L48)
* **Description**: Concurrent stats modifications read stale counters during sleep phases, causing incorrect reporting of bookings and revenue. Additionally, lazy initialization from DB upon restart could double-count the currently committed booking.
* **Code Change**:
  ```python
  # BEFORE (Fardin commit double-counting bug)
  with _lock:
      if room_id not in _stats:
          _load_stats_from_db(room_id, db)
      current = _stats.get(room_id, {"count": 0, "revenue": 0})
      # increments applied directly, causing double counts
      _stats[room_id] = {"count": count + 1, "revenue": revenue + price_cents}
  
  # AFTER (Final correct code)
  with _lock:
      if room_id not in _stats:
          _load_stats_from_db(room_id, db) # Loads committed state (includes new booking)
      else:
          # Only apply incremental updates in memory if already initialized
          current = _stats[room_id]
          _stats[room_id] = {"count": current["count"] + 1, "revenue": current["revenue"] + price_cents}
  ```
