# Task 4 Report: FastAPI 服务及 API 路由定义

## Execution Details
- **FastAPI Application (`main.py`)**:
  - Implemented `FastAPI` instance with title `"Hot News Needs Miner"`.
  - Added `@app.on_event("startup")` event handler to initialize the database and run the automatic cleanup of events older than 7 days.
  - Implemented GET `/api/events` endpoint to query and return pending events from the database.
  - Implemented POST `/api/trigger-crawl` to run `crawler.crawl_and_save_all()` and trigger automatic cleanup of old events.
  - Implemented POST `/api/events/{event_id}/analyze` to trigger the AI analyst to analyze the specific event and save the results in the database.
  - Mounted the `./static` directory at the root (`/`) using `StaticFiles` to serve static frontend files.
- **Unit Test Suite (`tests/test_main.py`)**:
  - Added unit tests for the startup event handler, verifying that `database.init_db()` and `database.delete_old_unanalyzed_events()` are called when the application starts.
  - Added success and failure tests for GET `/api/events`, mocking `database.get_pending_events()`.
  - Added success and failure tests for POST `/api/trigger-crawl`, mocking `crawler.crawl_and_save_all()` and `database.delete_old_unanalyzed_events()`.
  - Added success, error, and missing payload tests for POST `/api/events/{event_id}/analyze`, mocking `ai_analyst.trigger_event_analysis()`.
  - Added a test for the static files mount, ensuring that files in `./static` are served correctly.

## Test Verification Output
- **Execution note**: During execution, the terminal execution permission prompts for `pytest` timed out due to the non-interactive execution environment.
- **Action plan**: The API implementation and test suite have been fully written and structured. You can run the test suite to verify implementation correctness via:
  ```bash
  PYTHONPATH=. ./venv/bin/pytest tests/test_main.py -v
  ```
