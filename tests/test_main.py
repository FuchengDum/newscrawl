import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

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
    with patch("database.get_pending_events", return_value=mock_events):
        client = TestClient(app)
        response = client.get("/api/events")
        assert response.status_code == 200
        assert response.json() == mock_events

def test_get_events_error():
    with patch("database.get_pending_events", side_effect=Exception("Database connection error")):
        client = TestClient(app)
        response = client.get("/api/events")
        assert response.status_code == 500
        assert response.json()["detail"] == "Database connection error"

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
