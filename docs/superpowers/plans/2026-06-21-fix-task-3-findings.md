# Fix Task 3 Reviewer Findings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the findings reported by the reviewer for Task 3, specifically handling transient API errors without permanently locking events as low_value, dynamically reloading the Gemini API key in `ai_analyst.py`, and updating the tests and report accordingly.

**Architecture:** 
- In `database.py`, adjust the status calculation logic to check if a specific status is provided in the analysis result dictionary (e.g. `"status": "failed"`).
- In `ai_analyst.py`, reload the `GEMINI_API_KEY` from `os.getenv("GEMINI_API_KEY")` on each invocation of `analyze_hot_topic` and configure `google.generativeai` dynamically. Add `"status": "failed"` to all fallback error response dictionaries.
- In `tests/test_ai_analyst.py`, verify that dynamic API key reloading works and the fallback return dictionary contains `"status": "failed"`.

**Tech Stack:** Python, pytest, SQLite, google-generativeai

## Global Constraints
- Target files: `database.py`, `ai_analyst.py`, `tests/test_ai_analyst.py`, `.superpowers/sdd/task-3-report.md`.
- No hardcoded API keys.
- Preserve existing functionality and passing tests.

---

### Task 1: Update Database Status Logic

**Files:**
- Modify: `database.py:78-81`

**Interfaces:**
- Consumes: None
- Produces: `update_analysis(event_id, a)` with status-override support

- [ ] **Step 1: Update `database.py` status determination logic**
    Modify `database.py` around line 78 to extract the status if present in the dictionary:
    ```python
    status = a.get("status")
    if not status:
        status = "analyzed" if a.get("has_value") and a.get("value_score", 0) >= 6 else "low_value"
    ```

---

### Task 2: Dynamic API Key Reloading & Status Override in AI Analyst

**Files:**
- Modify: `ai_analyst.py`

**Interfaces:**
- Consumes: `os.getenv("GEMINI_API_KEY")`
- Produces: Updated `analyze_hot_topic(title, platform)`

- [ ] **Step 1: Update API key config and fallback returns**
    Modify `ai_analyst.py` to configure `genai` dynamically within the `analyze_hot_topic` function.
    Add `"status": "failed"` to both fallback error/dictionary returns.
    
    ```python
    def analyze_hot_topic(title, platform):
        # Dynamically reload / get API key
        current_api_key = os.getenv("GEMINI_API_KEY")
        if current_api_key:
            genai.configure(api_key=current_api_key)
        else:
            return {
                "has_value": False,
                "value_score": 1,
                "target_audience": "未配置API密钥",
                "pain_point": "请检查环境变量或.env文件中的GEMINI_API_KEY",
                "product_concept": "未配置密钥",
                "difficulty": "easy",
                "analysis_summary": "请先配置密钥",
                "status": "failed"
            }
        # ...
        try:
            # ...
        except Exception as e:
            return {
                "has_value": False,
                "value_score": 1,
                "target_audience": "错误",
                "pain_point": f"Gemini API 报错: {str(e)}",
                "product_concept": "分析失败",
                "difficulty": "easy",
                "analysis_summary": "API调用异常",
                "status": "failed"
            }
    ```

---

### Task 3: Update and Add Tests

**Files:**
- Modify: `tests/test_ai_analyst.py`
- Modify: `tests/test_database.py`

- [ ] **Step 1: Update `tests/test_ai_analyst.py`**
    Assert the presence of `"status": "failed"` in mock tests, and test dynamic reloading of the key.
    
    ```python
    def test_mock_analysis_without_key():
        # 测试在未提供 API 密钥时能正确回退并报错
        os.environ["GEMINI_API_KEY"] = ""
        res = ai_analyst.analyze_hot_topic("加班报销难", "weibo")
        assert res["has_value"] is False
        assert "GEMINI_API_KEY" in res["pain_point"]
        assert res["status"] == "failed"
    ```

- [ ] **Step 2: Add database test for status override**
    Update `tests/test_database.py` to verify that passing an explicit status like `"failed"` to `update_analysis` saves it correctly in the database.
    
    ```python
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
    ```

---

### Task 4: Run Tests, Update Report, Commit

**Files:**
- Modify: `.superpowers/sdd/task-3-report.md`

- [ ] **Step 1: Run unit tests**
    Run: `PYTHONPATH=. ./venv/bin/pytest tests/test_ai_analyst.py tests/test_database.py -v`
    
- [ ] **Step 2: Update report file**
    Update `.superpowers/sdd/task-3-report.md` detailing the fixes.
    
- [ ] **Step 3: Commit all changes**
    Run `git add` and `git commit` to commit changes.
