# Bug Report - CoWork REST API

This document details all 21 bugs identified and resolved in the CoWork REST API.

---

### Bug 1: Access Token Lifetime Expiry
* **File & Lines**: [app/auth.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/auth.py#L50)
* **Description**: The lifetime of the access token was computed as `timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 60)`, which evaluates to 900 minutes (15 hours) instead of 15 minutes (900 seconds).
* **Fix**: Removed the `* 60` multiplier to make it `timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)`.

---

### Bug 2: Logout Access Token Revocation Comparisons
* **File & Lines**: [app/auth.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/auth.py#L97)
* **Description**: Revoking an access token during logout added the token's `jti` to `_revoked_tokens`. However, the validation check in `get_token_payload` checked if the user ID (`sub`) was in `_revoked_tokens`, allowing revoked tokens to remain active.
* **Fix**: Changed the check to assert if `payload.get("jti")` is in `_revoked_tokens`.

---

### Bug 3: Duplicate Registration Returns Existing User
* **File & Lines**: [app/routers/auth.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/auth.py#L32-L43)
* **Description**: Registering a duplicate username in the same organization returned the existing user details with status `201 Created` instead of raising a `409 USERNAME_TAKEN` error.
* **Fix**: Raised `AppError(409, "USERNAME_TAKEN", "...")`. Added transaction rollback and handling of database constraints for concurrent duplicate registrations.

---

### Bug 4: Future Booking Past Start Time Grace Window
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L90)
* **Description**: The future check allowed bookings up to 5 minutes in the past due to `start <= now - timedelta(seconds=300)`.
* **Fix**: Removed the grace window by changing the check to `start <= now`.

---

### Bug 5: Booking Details Endpoint Overwriting Start Time
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L172)
* **Description**: The GET `/bookings/{id}` detail route overwrote the booking's `start_time` with the creation time `iso_utc(booking.created_at)`.
* **Fix**: Deleted this line.

---

### Bug 6: Timezone Offset Stripped instead of Converted
* **File & Lines**: [app/timeutils.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/timeutils.py#L11-L14)
* **Description**: The utility `parse_input_datetime` stripped timezone offsets using `dt.replace(tzinfo=None)` instead of converting them to UTC first, storing local wall-clock times as-is.
* **Fix**: Adjusted to UTC before stripping the timezone offset: `dt.astimezone(timezone.utc).replace(tzinfo=None)`.

---

### Bug 7: Infinite Reusability of Refresh Tokens
* **File & Lines**: [app/routers/auth.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/auth.py#L81-L93)
* **Description**: Refresh tokens were infinitely reusable as they were not checked for single-use rotation or invalidated upon ingestion.
* **Fix**: Tracked used refresh token `jti` identifiers in a revoked set, checking for reuse and invalidating them upon successful rotation.

---

### Bug 8: Missing Booking Minimum Duration Bounds
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L97)
* **Description**: Only the maximum duration bound (8 hours) was validated, allowing bookings with zero-hour or negative durations.
* **Fix**: Added validation to ensure duration is between `MIN_DURATION_HOURS` (1) and `MAX_DURATION_HOURS` (8).

---

### Bug 9: Overlapping Booking Operator Logic
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L54)
* **Description**: Overlap checking in `_has_conflict` used inclusive `<=` comparison, preventing back-to-back room bookings.
* **Fix**: Changed comparison operators to strict `<`.

---

### Bug 10: Bookings Pagination and Ordering Broken
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L142-L147)
* **Description**: The listing was sorted descending instead of ascending, offset skipped page 1 due to `page * limit`, and the page limit was hardcoded to `10` ignoring user inputs.
* **Fix**: Ordered by ascending `start_time` (ties by ascending `id`), calculated offsets as `(page - 1) * limit`, and respected the dynamic limit parameter.

---

### Bug 11: Cross-User Booking Leak
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L157-L170)
* **Description**: Non-admin users could read other members' bookings by knowing their booking IDs, as detail checks were only scoped by organization.
* **Fix**: Restricted view permissions to the owner or admins of the organization, raising `404 BOOKING_NOT_FOUND` otherwise.

---

### Bug 12: Cancellation Refund Tier Boundaries
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L207-L212)
* **Description**: A booking cancelled at exactly 48 hours notice fell into the 50% refund tier, and notice under 24 hours defaulted to 50% instead of 0%.
* **Fix**: Fixed notice comparison boundaries to match the 100%, 50%, and 0% tiers exactly.

---

### Bug 13: Refund Amount Rounding and Ledger Mismatch
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L214) and [app/services/refunds.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/services/refunds.py#L14-L17)
* **Description**: Cancel responses used round-to-even `round()` while `log_refund` used floating-point truncation, causing mismatches.
* **Fix**: Standardized calculations to use Python's `Decimal` module with `ROUND_HALF_UP` quantization, passing the exact cent values into the log ledger.

---

### Bug 14: CSV Export Cross-Org Data Leak
* **File & Lines**: [app/services/export.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/services/export.py#L48-L50) and [app/routers/admin.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/admin.py#L65-L74)
* **Description**: Export endpoint did not verify if the requested `room_id` belonged to the caller's organization under `include_all=True`, permitting data leaks.
* **Fix**: Checked room ownership in the router (raising `404 ROOM_NOT_FOUND` on violation) and forced all query routes in the service to remain org-scoped.

---

### Bug 15: Missing Cache Invalidation Gaps
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L121) and [app/routers/rooms.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/rooms.py#L56)
* **Description**: Reports remained stale because booking creation did not invalidate report caches, cancellations did not invalidate availability caches, and room creations did not invalidate reports.
* **Fix**: Added missing cache invalidation calls upon room/booking creations and cancellations.

---

### Bug 16: Lock-Ordering deadlock in Notifications
* **File & Lines**: [app/services/notifications.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/services/notifications.py#L24-L36)
* **Description**: `notify_created` acquired locks `_email` -> `_audit`, whereas `notify_cancelled` acquired them in reverse order, leading to concurrent deadlocks.
* **Fix**: Synchronized lock acquisition ordering (acquiring `_email` first) across both operations.

---

### Bug 17: Concurrent Booking Double Creation and Quotas
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L104-L123)
* **Description**: Concurrent booking requests could bypass conflict/quota constraints due to thread yields inside `time.sleep` calls.
* **Fix**: Wrapped verification checks and booking creation in a synchronized `booking_write_lock` block.

---

### Bug 18: Concurrent Cancellations and Double Refunds
* **File & Lines**: [app/routers/bookings.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/routers/bookings.py#L195-L224)
* **Description**: Simultaneous cancellation requests could bypass status verification and commit multiple refund logs.
* **Fix**: Wrapped the cancellation sequence in the `booking_write_lock`, refreshing the database object state inside the lock before checking status.

---

### Bug 19: Sequence Counter Race in Reference Code Generation
* **File & Lines**: [app/services/reference.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/services/reference.py#L17-L21)
* **Description**: Concurrent booking creations could read identical counter states before increments, generating duplicate reference codes.
* **Fix**: Protected reference code increments using a thread mutex lock.

---

### Bug 20: Rate Limit Verification Race Condition
* **File & Lines**: [app/services/ratelimit.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/services/ratelimit.py#L18-L26)
* **Description**: Concurrent request arrivals read identical stale timestamp buckets, bypassing request limits.
* **Fix**: Protected bucket reads and updates using a thread mutex lock.

---

### Bug 21: Lost Incremental Statistics Updates
* **File & Lines**: [app/services/stats.py](file:///d:/Hackathon/ICT_Fest_Hackathon_Preliminary/app/services/stats.py#L15-L27)
* **Description**: Concurrent stats modifications read stale counters during sleep phases, causing incorrect reporting of bookings and revenue.
* **Fix**: Wrapped statistics updates with a thread mutex lock.