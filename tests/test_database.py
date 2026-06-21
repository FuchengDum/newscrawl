import os
import pytest
import database

def setup_module(module):
    database.DB_FILE = "test_ainews.db"
    database.init_db()

def teardown_module(module):
    if os.path.exists("test_ainews.db"):
        os.remove("test_ainews.db")

def test_save_and_fetch():
    success = database.save_hot_event("如何评价新出的AI助手", "https://test.com", "zhihu", 9999)
    assert success is True
    
    events = database.get_pending_events()
    assert len(events) == 1
    assert events[0]["title"] == "如何评价新出的AI助手"
    
    # 重复保存同一标题应该返回 False
    duplicate = database.save_hot_event("如何评价新出的AI助手", "https://test.com", "zhihu", 9999)
    assert duplicate is False

def test_update_analysis_data():
    events = database.get_pending_events()
    event_id = events[0]["id"]
    
    analysis = {
        "has_value": True,
        "value_score": 8,
        "target_audience": "开发者",
        "pain_point": "日常写代码查文档慢",
        "product_concept": "AI助手快捷键插件",
        "difficulty": "easy",
        "analysis_summary": "极简AI助手"
    }
    database.update_analysis(event_id, analysis)
    
    with database.get_db_connection() as conn:
        row = conn.execute("SELECT * FROM need_analysis WHERE event_id = ?", (event_id,)).fetchone()
        assert row["status"] == "analyzed"
        assert row["value_score"] == 8
        assert row["target_audience"] == "开发者"

def test_on_delete_cascade():
    # Insert event
    title = "Test cascade event"
    success = database.save_hot_event(title, "https://cascade.com", "github", 100)
    assert success is True
    
    # Get the inserted event ID
    with database.get_db_connection() as conn:
        event = conn.execute("SELECT id FROM hot_events WHERE title = ?", (title,)).fetchone()
        assert event is not None
        event_id = event["id"]
        
        # Verify need_analysis entry exists
        analysis = conn.execute("SELECT * FROM need_analysis WHERE event_id = ?", (event_id,)).fetchone()
        assert analysis is not None
        
        # Delete hot_event
        conn.execute("DELETE FROM hot_events WHERE id = ?", (event_id,))
        conn.commit()
        
        # Verify need_analysis entry is gone (due to ON DELETE CASCADE)
        analysis_after = conn.execute("SELECT * FROM need_analysis WHERE event_id = ?", (event_id,)).fetchone()
        assert analysis_after is None

def test_delete_old_unanalyzed_events():
    # Insert 4 different events
    # Event A: old and pending (should be deleted)
    database.save_hot_event("Old Pending Event", "http://a.com", "reddit", 10)
    # Event B: old and low_value (should be deleted)
    database.save_hot_event("Old Low Value Event", "http://b.com", "reddit", 20)
    # Event C: old and analyzed (should be preserved)
    database.save_hot_event("Old Analyzed Event", "http://c.com", "reddit", 30)
    # Event D: new and pending (should be preserved)
    database.save_hot_event("New Pending Event", "http://d.com", "reddit", 40)
    
    # Get IDs and update timestamps/statuses
    from datetime import datetime, timedelta, timezone
    old_time = (datetime.now(timezone.utc) - timedelta(days=8)).strftime("%Y-%m-%d %H:%M:%S")
    
    with database.get_db_connection() as conn:
        # Get IDs
        id_a = conn.execute("SELECT id FROM hot_events WHERE title = 'Old Pending Event'").fetchone()["id"]
        id_b = conn.execute("SELECT id FROM hot_events WHERE title = 'Old Low Value Event'").fetchone()["id"]
        id_c = conn.execute("SELECT id FROM hot_events WHERE title = 'Old Analyzed Event'").fetchone()["id"]
        id_d = conn.execute("SELECT id FROM hot_events WHERE title = 'New Pending Event'").fetchone()["id"]
        
        # Update created_at for A, B, C
        conn.execute("UPDATE hot_events SET created_at = ? WHERE id IN (?, ?, ?)", (old_time, id_a, id_b, id_c))
        
        # Update status for B to 'low_value'
        conn.execute("UPDATE need_analysis SET status = 'low_value' WHERE event_id = ?", (id_b,))
        
        # Update status for C to 'analyzed'
        conn.commit()
    
    # Update analysis for C to high value (status='analyzed')
    database.update_analysis(id_c, {
        "has_value": True,
        "value_score": 7,
        "target_audience": "anyone",
        "pain_point": "none",
        "product_concept": "idea",
        "difficulty": "easy",
        "analysis_summary": "summary"
    })
    
    # Run the cleanup function
    database.delete_old_unanalyzed_events()
    
    # Verify DB contents
    with database.get_db_connection() as conn:
        # A and B should be deleted
        assert conn.execute("SELECT * FROM hot_events WHERE id = ?", (id_a,)).fetchone() is None
        assert conn.execute("SELECT * FROM hot_events WHERE id = ?", (id_b,)).fetchone() is None
        
        # C and D should be preserved
        assert conn.execute("SELECT * FROM hot_events WHERE id = ?", (id_c,)).fetchone() is not None
        assert conn.execute("SELECT * FROM hot_events WHERE id = ?", (id_d,)).fetchone() is not None
        
        # Also need_analysis for A and B should be gone due to CASCADE
        assert conn.execute("SELECT * FROM need_analysis WHERE event_id = ?", (id_a,)).fetchone() is None
        assert conn.execute("SELECT * FROM need_analysis WHERE event_id = ?", (id_b,)).fetchone() is None
        
        # and C and D need_analysis should be preserved
        assert conn.execute("SELECT * FROM need_analysis WHERE event_id = ?", (id_c,)).fetchone() is not None
        assert conn.execute("SELECT * FROM need_analysis WHERE event_id = ?", (id_d,)).fetchone() is not None

def test_update_analysis_status_override():
    # Setup event
    database.save_hot_event("Failed Analysis Event", "http://failed.com", "weibo", 50)
    events = database.get_pending_events()
    event_id = [e for e in events if e["title"] == "Failed Analysis Event"][0]["id"]
    
    analysis = {
        "has_value": False,
        "value_score": 1,
        "target_audience": "错误",
        "pain_point": "Gemini API 报错",
        "product_concept": "分析失败",
        "difficulty": "easy",
        "analysis_summary": "API调用异常",
        "status": "failed"
    }
    database.update_analysis(event_id, analysis)
    
    with database.get_db_connection() as conn:
        row = conn.execute("SELECT * FROM need_analysis WHERE event_id = ?", (event_id,)).fetchone()
        assert row["status"] == "failed"
