# Task 1 Report: SQLite Database & Dependency Configuration

## Execution Details
- **Dependency Configuration**: Created `requirements.txt` containing standard dependencies.
- **Database Schema & Logic (`database.py`)**:
  - Implemented `get_db_connection()`, `init_db()`, `save_hot_event()`, `get_pending_events()`, `update_analysis()`, and `delete_old_unanalyzed_events()`.
  - Enforced SQLite Foreign Keys: `conn.execute("PRAGMA foreign_keys = ON;")` is executed immediately after connection initialization.
  - Standardized on UTC Timezone: Updated both `update_analysis()` and `delete_old_unanalyzed_events()` to use UTC timezone-aware datetimes (`datetime.now(timezone.utc)`).
- **Unit Tests (`tests/test_database.py`)**:
  - Added unit test covering `ON DELETE CASCADE` verifying that deleting a `hot_event` cleans up the corresponding `need_analysis` row.
  - Added unit test covering `delete_old_unanalyzed_events()` verifying it correctly removes old unanalyzed events (older than 7 days) and low-value events while preserving analyzed ones and newer pending events.

## Test Verification Output
- **Command Run**: `PYTHONPATH=. ./venv/bin/pytest tests/test_database.py -v`
- **Output**:
  ```
  tests/test_database.py::test_save_and_fetch PASSED                       [ 25%]
  tests/test_database.py::test_update_analysis_data PASSED                 [ 50%]
  tests/test_database.py::test_on_delete_cascade PASSED                    [ 75%]
  tests/test_database.py::test_delete_old_unanalyzed_events PASSED         [100%]

  ============================== 4 passed in 0.02s ===============================
  ```
