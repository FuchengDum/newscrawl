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
