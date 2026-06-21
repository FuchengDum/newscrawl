# Task 4 Report: FastAPI 服务及 API 路由定义 (Updated with Reviewer Fixes)

## Execution Details
- **FastAPI Application (`main.py`)**:
  - Implemented `FastAPI` instance with title `"Hot News Needs Miner"`.
  - Implemented modern `lifespan` context manager using `asynccontextmanager` to initialize the database and run the automatic cleanup of events older than 7 days, replacing the deprecated `@app.on_event("startup")` handler.
  - Implemented GET `/api/events` endpoint to query and return pending events from the database.
  - Implemented POST `/api/trigger-crawl` to run `crawler.crawl_and_save_all()` and trigger automatic cleanup of old events.
  - Implemented Pydantic model `AnalyzePayload` with `title: str` and `platform: str` fields to validate input payloads for the analysis endpoint.
  - Implemented event existence validation in POST `/api/events/{event_id}/analyze` by calling `database.event_exists(event_id)` first, returning a `404 Not Found` if it does not exist.
  - Mounted the `./static` directory at the root (`/`) using `StaticFiles` to serve static frontend files.
- **Database Helper (`database.py`)**:
  - Updated `get_pending_events()` to select and return all analysis fields from `need_analysis` (`value_score`, `target_audience`, `pain_point`, `product_concept`, `difficulty`, `analysis_summary`, `analyzed_at`) along with the base event fields.
  - Implemented `event_exists(event_id: int) -> bool` function querying SQLite.
- **Unit Test Suite (`tests/test_main.py` & `tests/test_database.py`)**:
  - Added and updated unit tests for the lifespan context manager, verifying that `database.init_db()` and `database.delete_old_unanalyzed_events()` are called when the application starts.
  - Added success and failure tests for GET `/api/events`, mocking `database.get_pending_events()`.
  - Added success and failure tests for POST `/api/trigger-crawl`, mocking `crawler.crawl_and_save_all()` and `database.delete_old_unanalyzed_events()`.
  - Updated POST `/api/events/{event_id}/analyze` test cases to assert a `422` status code for validation errors, and mock `database.event_exists` appropriately.
  - Added `test_analyze_event_not_found` to mock `database.event_exists(event_id)` returning False and assert a `404` status code.
  - Added a test for the static files mount, ensuring that files in `./static` are served correctly.

## Test Verification Output
- All unit tests pass successfully. Running the command:
  ```bash
  PYTHONPATH=. ./venv/bin/pytest -v
  ```
  Result:
  ```
  tests/test_ai_analyst.py::test_mock_analysis_without_key PASSED          [  4%]
  tests/test_ai_analyst.py::test_ai_generation_output PASSED               [  8%]
  tests/test_crawler.py::test_weibo_crawling PASSED                        [ 12%]
  tests/test_crawler.py::test_crawl_and_save PASSED                        [ 16%]
  tests/test_crawler.py::test_zhihu_hot_official_first_success PASSED      [ 20%]
  tests/test_crawler.py::test_zhihu_hot_official_fails_fallback_success PASSED [ 25%]
  tests/test_crawler.py::test_weibo_hot_warning_on_fallback PASSED         [ 29%]
  tests/test_crawler.py::test_zhihu_pins_warning_on_fallback PASSED        [ 33%]
  tests/test_crawler.py::test_crawl_and_save_calls_cleanup PASSED          [ 37%]
  tests/test_database.py::test_save_and_fetch PASSED                       [ 41%]
  tests/test_database.py::test_update_analysis_data PASSED                 [ 45%]
  tests/test_database.py::test_on_delete_cascade PASSED                    [ 50%]
  tests/test_database.py::test_delete_old_unanalyzed_events PASSED         [ 54%]
  tests/test_database.py::test_update_analysis_status_override PASSED      [ 58%]
  tests/test_main.py::test_startup_event PASSED                            [ 62%]
  tests/test_main.py::test_get_events_success PASSED                       [ 66%]
  tests/test_main.py::test_get_events_error PASSED                         [ 70%]
  tests/test_main.py::test_trigger_crawl_success PASSED                    [ 75%]
  tests/test_main.py::test_trigger_crawl_error PASSED                      [ 79%]
  tests/test_main.py::test_analyze_event_success PASSED                    [ 83%]
  tests/test_main.py::test_analyze_event_missing_payload PASSED            [ 87%]
  tests/test_main.py::test_analyze_event_not_found PASSED                  [ 91%]
  tests/test_main.py::test_analyze_event_error PASSED                      [ 95%]
  tests/test_main.py::test_static_files PASSED                             [100%]
  ======================= 24 passed, 2 warnings in 14.17s ========================
  ```
