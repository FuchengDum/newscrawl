# Task 2 Report: Crawler & RSSHub Fallback Mechanism

## Execution Details
- **Crawler Implementation (`crawler.py`)**:
  - Implemented `fetch_weibo_hot()` which tries Weibo's AJAX hotSearch API, and falls back to `fetch_weibo_rss_fallback()` using RSSHub mirrors (`RSSHUB_MIRRORS`) in case of 403 or network failure.
  - Implemented `fetch_zhihu_hot()` which prioritizes the RSSHub mirrors (due to strict API IP rate limits) and falls back to the native `api.zhihu.com` client API.
  - Implemented `fetch_zhihu_pins()` to fetch daily Weibo-like ideas / pins from the RSSHub mirrors.
  - Implemented `crawl_and_save_all()` which initializes the database, crawls all three platforms, and saves new events via `database.save_hot_event()`.
- **Unit Tests (`tests/test_crawler.py`)**:
  - Implemented `test_weibo_crawling()` to verify that Weibo's hot search items are fetched as a list containing the platform name and title.
  - Implemented `test_crawl_and_save()` to verify `crawl_and_save_all()` inserts events into the database successfully and returns the correct summary dictionary keys.

## Test Verification Output
- **Command Run**: `PYTHONPATH=. ./venv/bin/pytest tests/test_crawler.py -v`
- **Output**:
  ```
  tests/test_crawler.py::test_weibo_crawling PASSED                        [ 50%]
  tests/test_crawler.py::test_crawl_and_save PASSED                        [100%]

  ============================== 2 passed in 35.49s ==============================
  ```
