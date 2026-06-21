# Task 2 Report: Crawler Enhancements, Fallback Logic, and Error Handling Fixes

This report details the enhancements and bug fixes implemented in [crawler.py](file:///Users/dum/google/proj/ainews/crawler.py) to address the reviewer's feedback for Task 2.

---

## 1. Inverted Fallback Logic in `fetch_zhihu_hot()`

### Problem
Previously, `fetch_zhihu_hot()` tried the RSSHub mirrors first and only fell back to the official API when the mirrors failed. This logic was inverted, as the official API should be the primary data source and RSSHub mirrors should serve as fallbacks.

### Solution
We restructured `fetch_zhihu_hot()` to:
1. Attempt to fetch from the official API (`https://api.zhihu.com/topstory/hot-lists/total?limit=50`) first.
2. Return the scraped results with `fallback = False` upon success.
3. Catch any `Exception` during the official API request, print a warning, and proceed to loop through the `RSSHUB_MIRRORS` list.
4. Return `fallback = True` if a mirror succeeds, or `([], True)` if all mirrors and the official API fail.

---

## 2. Automatic Database Cleanup in `crawl_and_save_all()`

### Problem
After crawling data, old unanalyzed events could clutter the database. We needed to clean up unanalyzed events older than 7 days automatically during the crawl cycle.

### Solution
Inside `crawl_and_save_all()`, after saving the retrieved events for Weibo, Zhihu, and Zhihu Pins to the database, we inserted a call to `database.delete_old_unanalyzed_events()`. This ensures that every run of the crawler automatically cleans up pending, low-value, or failed events that are older than 7 days.

---

## 3. Logging Warnings on Fallback

### Problem
When a crawler falls back to RSSHub mirrors, there was no warning or indication printed or logged, making it hard to notice when official endpoints failed.

### Solution
We added warning messages using `print()`:
- **Weibo Hot (`fetch_weibo_hot()`):** Prints a warning when the Weibo home page handshake fails or the AJAX API request fails, before calling `fetch_weibo_rss_fallback()`.
- **Weibo RSS Fallback (`fetch_weibo_rss_fallback()`):** Prints a warning when a specific RSSHub mirror fails to fetch Weibo hot news.
- **Zhihu Hot (`fetch_zhihu_hot()`):** Prints a warning when the official API fails, and also when any specific RSSHub mirror fails.
- **Zhihu Pins (`fetch_zhihu_pins()`):** Prints a warning when an RSSHub mirror request fails.

---

## 4. Robust Zhihu Popularity Parsing

### Problem
The popularity parsing logic used `int(metrics.replace(" 万热度", "").replace("万", "").strip()) * 10000`. If `metrics` was a float representation such as `"123.4"`, passing it directly to `int()` threw a `ValueError`, falling back to the default popularity of `500000` instead of parsing it correctly.

### Solution
We updated the parsing expression to first convert the cleaned string to a `float`, multiply by `10000`, and then cast to an `int`:
```python
val_str = metrics.replace(" 万热度", "").replace("万", "").strip()
popularity = int(float(val_str) * 10000)
```
This safely converts strings like `"123.4"` to `1234000` instead of throwing a `ValueError`.

---

## 5. Test Suite Verification

We added comprehensive unit tests using `unittest.mock.patch` in [tests/test_crawler.py](file:///Users/dum/google/proj/ainews/tests/test_crawler.py):
- `test_zhihu_hot_official_first_success()`: Verifies the official API is tried first and returns `fallback = False`, checking the correct popularity parsing for float strings like `"123.4 万热度"`.
- `test_zhihu_hot_official_fails_fallback_success()`: Verifies that when the official API fails, a warning is printed and RSSHub mirrors are queried as a fallback, returning `fallback = True`.
- `test_weibo_hot_warning_on_fallback()`: Verifies a warning is logged when Weibo official APIs fail and fall back to mirrors.
- `test_zhihu_pins_warning_on_fallback()`: Verifies warnings are logged when RSSHub mirror requests fail.
- `test_crawl_and_save_calls_cleanup()`: Verifies that `database.delete_old_unanalyzed_events()` is executed inside `crawl_and_save_all()`.
