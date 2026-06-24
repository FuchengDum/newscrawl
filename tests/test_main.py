import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app, batch_state

def test_startup_event():
    with patch("database.init_db") as mock_init, \
         patch("database.delete_old_unanalyzed_events") as mock_delete:
        with TestClient(app) as client:
            mock_init.assert_called_once()
            mock_delete.assert_called_once()

def test_get_events_success():
    mock_events = [
        {"id": 1, "title": "Test Event 1", "url": "http://test1.com", "platform": "weibo", "popularity": 100, "status": "pending"},
        {"id": 2, "title": "Test Event 2", "url": "http://test2.com", "platform": "zhihu", "popularity": 200, "status": "analyzed"}
    ]
    with patch("database.get_events_filtered", return_value=mock_events):
        client = TestClient(app)
        response = client.get("/api/events")
        assert response.status_code == 200
        assert response.json() == mock_events

def test_get_events_with_filters():
    mock_events = [{"id": 1, "title": "T", "url": "", "platform": "weibo", "popularity": 100, "status": "pending"}]
    with patch("database.get_events_filtered", return_value=mock_events) as mock_fn:
        client = TestClient(app)
        response = client.get("/api/events?date=2026-06-23&platform=weibo&status=pending&difficulty=easy&show_low_value=false")
        assert response.status_code == 200
        mock_fn.assert_called_once_with(
            date="2026-06-23",
            platform="weibo",
            status="pending",
            difficulty="easy",
            show_low_value=False
        )

def test_get_events_all_filters_become_none():
    """platform/status/difficulty='all' should be passed as None to db."""
    with patch("database.get_events_filtered", return_value=[]) as mock_fn:
        client = TestClient(app)
        response = client.get("/api/events?platform=all&status=all&difficulty=all")
        assert response.status_code == 200
        mock_fn.assert_called_once_with(
            date=None,
            platform=None,
            status=None,
            difficulty=None,
            show_low_value=True
        )

def test_get_events_error():
    with patch("database.get_events_filtered", side_effect=Exception("Database connection error")):
        client = TestClient(app)
        response = client.get("/api/events")
        assert response.status_code == 500
        assert response.json()["detail"] == "Database connection error"

def test_get_dates_success():
    with patch("database.get_available_dates", return_value=["2026-06-23", "2026-06-21"]):
        client = TestClient(app)
        response = client.get("/api/dates")
        assert response.status_code == 200
        assert response.json() == {"dates": ["2026-06-23", "2026-06-21"]}

def test_get_dates_error():
    with patch("database.get_available_dates", side_effect=Exception("DB error")):
        client = TestClient(app)
        response = client.get("/api/dates")
        assert response.status_code == 500

def test_batch_analyze_starts():
    # Reset global state before test
    with batch_state["lock"]:
        batch_state["running"] = False
    pending = [(1, "热点A", "weibo"), (2, "热点B", "zhihu")]
    with patch("database.get_batch_pending", return_value=pending), \
         patch("threading.Thread") as mock_thread:
        mock_thread.return_value.start = MagicMock()
        client = TestClient(app)
        response = client.post("/api/batch-analyze", json={"date": "2026-06-23", "platform": "all"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["total"] == 2
    # Reset again after test so subsequent tests are clean
    with batch_state["lock"]:
        batch_state["running"] = False

def test_batch_analyze_empty():
    # Ensure not running before this test
    with batch_state["lock"]:
        batch_state["running"] = False
    with patch("database.get_batch_pending", return_value=[]):
        client = TestClient(app)
        response = client.post("/api/batch-analyze", json={"date": "2026-06-23"})
        assert response.status_code == 200
        assert response.json()["status"] == "empty"

def test_batch_analyze_status():
    client = TestClient(app)
    response = client.get("/api/batch-analyze/status")
    assert response.status_code == 200
    data = response.json()
    assert "running" in data
    assert "total" in data
    assert "completed" in data
    assert "failed" in data
    assert "failed_titles" in data

def test_generate_report_success():
    mock_events = [
        {"id": 1, "title": "热点X", "platform": "weibo", "value_score": 9,
         "target_audience": "开发者", "pain_point": "效率低", "product_concept": "AI工具",
         "difficulty": "medium", "analysis_summary": "很有价值", "url": "", "popularity": 100, "status": "analyzed"}
    ]
    with patch("database.get_report_data", return_value=mock_events), \
         patch("ai_analyst.generate_daily_report_markdown", return_value="# Report") as mock_md, \
         patch("builtins.open", MagicMock()), \
         patch("os.makedirs"):
        client = TestClient(app)
        response = client.post("/api/report/2026-06-23")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "html" in data
        assert "markdown" in data
        mock_md.assert_called_once_with("2026-06-23", mock_events)

def test_generate_report_no_events():
    with patch("database.get_report_data", return_value=[]):
        client = TestClient(app)
        response = client.post("/api/report/2026-06-23")
        assert response.status_code == 404

def test_trigger_crawl_success():
    mock_summary = {
        "weibo_inserted": 5,
        "weibo_fallback": False,
        "zhihu_inserted": 10,
        "zhihu_fallback": False,
        "zhihu_pin_inserted": 3,
        "zhihu_pin_fallback": False
    }
    with patch("crawler.crawl_and_save_all", return_value=mock_summary) as mock_crawl, \
         patch("database.delete_old_unanalyzed_events") as mock_delete:
        client = TestClient(app)
        response = client.post("/api/trigger-crawl")
        assert response.status_code == 200
        assert response.json() == {"status": "success", "summary": mock_summary}
        mock_crawl.assert_called_once()
        mock_delete.assert_called_once()

def test_trigger_crawl_error():
    with patch("crawler.crawl_and_save_all", side_effect=Exception("Crawler failed")):
        client = TestClient(app)
        response = client.post("/api/trigger-crawl")
        assert response.status_code == 500
        assert response.json()["detail"] == "Crawler failed"

def test_analyze_event_success():
    event_id = 42
    payload = {"title": "AI is taking over", "platform": "weibo"}
    mock_analysis = {
        "has_value": True,
        "value_score": 8,
        "target_audience": "developers",
        "pain_point": "manual coding",
        "product_concept": "AI agent",
        "difficulty": "medium",
        "analysis_summary": "Summary text"
    }
    with patch("ai_analyst.trigger_event_analysis", return_value=mock_analysis) as mock_trigger, \
         patch("database.event_exists", return_value=True) as mock_exists:
        client = TestClient(app)
        response = client.post(f"/api/events/{event_id}/analyze", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "success", "analysis": mock_analysis}
        mock_trigger.assert_called_once_with(event_id, payload["title"], payload["platform"])
        mock_exists.assert_called_once_with(event_id)

def test_analyze_event_missing_payload():
    client = TestClient(app)
    # Missing platform
    response = client.post("/api/events/42/analyze", json={"title": "AI is taking over"})
    assert response.status_code == 422

    # Missing title
    response = client.post("/api/events/42/analyze", json={"platform": "weibo"})
    assert response.status_code == 422

    # Empty payload
    response = client.post("/api/events/42/analyze", json={})
    assert response.status_code == 422

def test_analyze_event_not_found():
    event_id = 42
    payload = {"title": "AI is taking over", "platform": "weibo"}
    with patch("database.event_exists", return_value=False) as mock_exists:
        client = TestClient(app)
        response = client.post(f"/api/events/{event_id}/analyze", json=payload)
        assert response.status_code == 404
        assert response.json()["detail"] == "Event not found"
        mock_exists.assert_called_once_with(event_id)

def test_analyze_event_error():
    event_id = 42
    payload = {"title": "AI is taking over", "platform": "weibo"}
    with patch("ai_analyst.trigger_event_analysis", side_effect=Exception("Gemini API Quota Exceeded")) as mock_trigger, \
         patch("database.event_exists", return_value=True) as mock_exists:
        client = TestClient(app)
        response = client.post(f"/api/events/{event_id}/analyze", json=payload)
        assert response.status_code == 500
        assert response.json()["detail"] == "Gemini API Quota Exceeded"
        mock_exists.assert_called_once_with(event_id)

def test_static_files():
    # Write a temporary file in the static directory to test serving
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    test_file_path = os.path.join(static_dir, "test_file.txt")
    
    # Ensure static directory exists
    os.makedirs(static_dir, exist_ok=True)
    
    with open(test_file_path, "w", encoding="utf-8") as f:
        f.write("Hello World")
        
    try:
        client = TestClient(app)
        response = client.get("/test_file.txt")
        assert response.status_code == 200
        assert response.text == "Hello World"
    finally:
        if os.path.exists(test_file_path):
            os.remove(test_file_path)

def test_batch_analyze_with_limit():
    with batch_state["lock"]:
        batch_state["running"] = False
    
    pending = [(i, f"热点_{i}", "weibo") for i in range(1, 26)]
    
    with patch("database.get_batch_pending", return_value=pending), \
         patch("database.reset_event_status_to_pending") as mock_reset, \
         patch("threading.Thread") as mock_thread:
        mock_thread.return_value.start = MagicMock()
        
        client = TestClient(app)
        response = client.post("/api/batch-analyze", json={"date": "2026-06-23", "platform": "all"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["total"] == 20
        assert data["original_total"] == 25
        assert data["limit"] == 20
        
        expected_ids = [i for i in range(1, 21)]
        mock_reset.assert_called_once_with(expected_ids)
        
    with batch_state["lock"]:
        batch_state["running"] = False
