# Environment Variable Configuration for AI Analyst Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure API endpoints, API keys, and models dynamically through environment variables in `ai_analyst.py` instead of hardcoding them, supporting model switching on the primary call, and verifying via pytest.

**Architecture:** Use `os.getenv` to fetch configurations from environment variables loaded via `dotenv`. Support comma-separated strings for multiple models. Generalize fallback triggering based on fallback configuration presence.

**Tech Stack:** Python, `dotenv`, `requests`, `pytest`.

## Global Constraints
- PEP 8 compliance, clear structure.
- Full type hinting for any new helper functions or modified signatures.
- Detailed Google-style docstrings for any modified/new functions.
- Run tests and commit after each task.

---

### Task 1: Update Environment Configurations (.env)

**Files:**
- Modify: `.env`

**Interfaces:**
- Produces: Environment variables `GEMINI_API_URL`, `GEMINI_MODEL`, `FALLBACK_API_URL`, `FALLBACK_API_KEY`, `FALLBACK_MODELS`.

- [ ] **Step 1: Write configuration defaults to `.env`**

  Modify [`.env`](file:///Users/dum/google/proj/ainews/.env) to include all fallback and primary configurations.

  ```ini
  GEMINI_API_KEY=sk-4OkOspCV7Bva6xPcoNtnU3rGuafPWtV9JrHdSATTBKhMnOGH
  GEMINI_MODEL=gemini-2.5-flash,gemini-1.5-flash
  GEMINI_API_URL=https://elysiver.h-e.top/v1/chat/completions
  FALLBACK_API_URL=https://wzw.pp.ua/v1/chat/completions
  FALLBACK_API_KEY=9NJJqjmYYJSmiZYYsitQrk8AvjnF5g8rCsIeDoTWeJpS4wGu
  FALLBACK_MODELS=deepseek-ai/deepseek-v4-flash,deepseek-ai/deepseek-v4-pro
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add .env
  git commit -m "config: extract hardcoded defaults into .env"
  ```

---

### Task 2: Implement Environment Variable Config Loading & Model Switching

**Files:**
- Modify: `ai_analyst.py`

**Interfaces:**
- Consumes: Environment variables from `.env` loaded via `load_dotenv()`.
- Produces: Updated `analyze_hot_topic` signature & logic.

- [ ] **Step 1: Write the failing tests first in `tests/test_ai_analyst.py` (TDD)**

  Add `test_ai_primary_model_switching` to [`tests/test_ai_analyst.py`](file:///Users/dum/google/proj/ainews/tests/test_ai_analyst.py).

  ```python
  def test_ai_primary_model_switching():
      from unittest.mock import patch, MagicMock
      import requests

      def mock_post_side_effect(url, headers, json_payload, timeout=30):
          model = json_payload.get("model")
          if model == "gemini-2.5-flash":
              response = MagicMock()
              response.status_code = 500
              response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error", response=response)
              return response
          elif model == "gemini-1.5-flash":
              response = MagicMock()
              response.json.return_value = {
                  "choices": [
                      {
                          "message": {
                              "content": '{"has_value": true, "value_score": 7, "target_audience": "开发者", "pain_point": "重复编写代码", "product_concept": "AI辅助工具", "difficulty": "easy", "analysis_summary": "切换模型成功"}'
                          }
                      }
                  ]
              }
              return response
          else:
              raise ValueError(f"Unexpected model {model}")

      with patch("requests.post", side_effect=mock_post_side_effect) as mock_post:
          ai_analyst._attempted_models.clear()
          ai_analyst._successful_models.clear()
          
          old_key = os.environ.get("GEMINI_API_KEY")
          old_models = os.environ.get("GEMINI_MODEL")
          
          os.environ["GEMINI_API_KEY"] = "mock_key"
          os.environ["GEMINI_MODEL"] = "gemini-2.5-flash,gemini-1.5-flash"
          
          try:
              res = ai_analyst.analyze_hot_topic("程序员脱发问题", "zhihu")
              assert res["has_value"] is True
              assert res["value_score"] == 7
              assert res["analysis_summary"] == "切换模型成功"
              
              called_models = [kwargs["json"]["model"] for args, kwargs in mock_post.call_args_list]
              assert "gemini-2.5-flash" in called_models
              assert "gemini-1.5-flash" in called_models
          finally:
              if old_key is not None:
                  os.environ["GEMINI_API_KEY"] = old_key
              else:
                  os.environ.pop("GEMINI_API_KEY", None)
              if old_models is not None:
                  os.environ["GEMINI_MODEL"] = old_models
              else:
                  os.environ.pop("GEMINI_MODEL", None)
  ```

- [ ] **Step 2: Run pytest to ensure the new test fails**

  Run: `PYTHONPATH=. ./venv/bin/pytest tests/test_ai_analyst.py::test_ai_primary_model_switching`
  Expected: FAIL (or errors out because of unimplemented configuration/switching logic)

- [ ] **Step 3: Update configuration loading and model switching in `ai_analyst.py`**

  Modify the code in [`ai_analyst.py`](file:///Users/dum/google/proj/ainews/ai_analyst.py):
  
  ```python
      # Replace lines 103-104 with:
      api_url = os.getenv("GEMINI_API_URL")
      model_raw = os.getenv("GEMINI_MODEL", "")
      primary_models = [m.strip() for m in model_raw.split(",") if m.strip()]

      # Replace lines 125-140 with:
      # First stage: Primary call loop
      success = False
      analysis = None
      last_error = None
      
      for model_name in primary_models:
          success, analysis, last_error = _call_openai_compatible_api(
              api_url, api_key, model_name, prompt, max_retries=3
          )
          if success:
              break

      # Second stage: Fallback call loop
      fb_url = os.getenv("FALLBACK_API_URL")
      fb_key = os.getenv("FALLBACK_API_KEY")
      fb_models_raw = os.getenv("FALLBACK_MODELS", "")
      fb_models = [m.strip() for m in fb_models_raw.split(",") if m.strip()]

      if not success and fb_url and fb_key and fb_models:
          for fb_model in fb_models:
              success, analysis, fb_error = _call_openai_compatible_api(
                  fb_url, fb_key, fb_model, prompt, max_retries=2
              )
              if success:
                  break
              else:
                  last_error = fb_error
  ```

- [ ] **Step 4: Update `tests/test_ai_analyst.py::test_ai_generation_failover_refactored`**

  Modify `test_ai_generation_failover_refactored` in [`tests/test_ai_analyst.py`](file:///Users/dum/google/proj/ainews/tests/test_ai_analyst.py) to set fallback variables:
  ```python
          os.environ["GEMINI_API_KEY"] = "mock_key"
          old_url = os.environ.get("GEMINI_API_URL")
          os.environ["GEMINI_API_URL"] = "https://elysiver.h-e.top/v1/chat/completions"
          
          old_fb_url = os.environ.get("FALLBACK_API_URL")
          old_fb_key = os.environ.get("FALLBACK_API_KEY")
          old_fb_models = os.environ.get("FALLBACK_MODELS")
          
          os.environ["FALLBACK_API_URL"] = "https://wzw.pp.ua/v1/chat/completions"
          os.environ["FALLBACK_API_KEY"] = "mock_fallback_key"
          os.environ["FALLBACK_MODELS"] = "deepseek-ai/deepseek-v4-flash,deepseek-ai/deepseek-v4-pro"
          
          try:
              ...
          finally:
              ...
              if old_fb_url is not None:
                  os.environ["FALLBACK_API_URL"] = old_fb_url
              else:
                  os.environ.pop("FALLBACK_API_URL", None)
              if old_fb_key is not None:
                  os.environ["FALLBACK_API_KEY"] = old_fb_key
              else:
                  os.environ.pop("FALLBACK_API_KEY", None)
              if old_fb_models is not None:
                  os.environ["FALLBACK_MODELS"] = old_fb_models
              else:
                  os.environ.pop("FALLBACK_MODELS", None)
  ```

- [ ] **Step 5: Run pytest to verify all tests pass**

  Run: `PYTHONPATH=. ./venv/bin/pytest`
  Expected: PASS

- [ ] **Step 6: Commit**

  ```bash
  git add ai_analyst.py tests/test_ai_analyst.py
  git commit -m "feat: implement dynamic configuration & model switching for AI Analyst"
  ```
