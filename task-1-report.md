# Task 1 Report: Database Connection Leak and Transaction Safety Fixes

## 1. SQLite Connection Leak (Resource Leak) Fix

### Problem
In `database.py`, functions opened connections using `get_db_connection()`, but these connections were never closed. Since SQLite connection context managers (`with conn:`) only manage transactions (committing on success, rolling back on exception) and do not close the connection itself, this resulted in resource leaks.

### Solution
We wrapped the connection lifecycle in `try...finally` blocks across all five target functions:
- `init_db()`
- `save_hot_event()`
- `get_pending_events()`
- `update_analysis()`
- `delete_old_unanalyzed_events()`

This guarantees that `conn.close()` is always executed on every connection opened, even if an exception occurs during execution.

---

## 2. Transaction Safety in `save_hot_event`

### Problem
Previously, the `try...except sqlite3.IntegrityError` block in `save_hot_event` was placed *inside* the `with conn:` transaction context manager:
```python
with get_db_connection() as conn:
    try:
        # DB operations...
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
```
Because the exception was caught inside the context manager, the context manager never received the exception and therefore did not trigger a rollback on failure.

### Solution
We moved the `try...except sqlite3.IntegrityError` block to the outside of the `with conn:` context manager:
```python
def save_hot_event(title, url, platform, popularity):
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO hot_events (title, url, platform, popularity) VALUES (?, ?, ?, ?)",
                (title, url, platform, popularity)
            )
            event_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO need_analysis (event_id, status) VALUES (?, 'pending')",
                (event_id,)
            )
        return True
    except sqlite3.IntegrityError:
        # 标题已存在，跳过插入
        return False
    finally:
        conn.close()
```
Now, any `IntegrityError` raised inside the `with conn:` block propagates to the context manager, triggering an automatic rollback of the transaction before the exception is caught by the outer `except sqlite3.IntegrityError:` block. The connection is then safely closed in the `finally` block.
