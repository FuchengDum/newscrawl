# Design Spec: Environment Variable Configuration for AI Analyst

This document outlines the design to move hardcoded API configurations (endpoints, keys, and models) from `ai_analyst.py` into environment variables, loadable via `.env`. It also introduces model switching support for the primary AI call.

## User Review Required

> [!IMPORTANT]
> - All default URL endpoints, API keys, and models will be defined in the `.env` file instead of Python source code.
> - The primary `GEMINI_MODEL` environment variable will support comma-separated model names (e.g. `gemini-2.5-flash,gemini-1.5-flash`), which will be tried sequentially.
> - The failover trigger condition will be generalized to detect the presence of fallback environment variables instead of hardcoding a substring check for `"elysiver.h-e.top"`.

## Proposed Changes

### Configuration Layer

#### [MODIFY] [ai_analyst.py](file:///Users/dum/google/proj/ainews/ai_analyst.py)

- Load configurations dynamically inside `analyze_hot_topic` using `os.getenv`.
- The following configurations will be retrieved:
  - `GEMINI_API_URL`
  - `GEMINI_MODEL` (parsed as a list of strings split by commas)
  - `FALLBACK_API_URL`
  - `FALLBACK_API_KEY`
  - `FALLBACK_MODELS` (parsed as a list of strings split by commas)
- Implement sequential model switching for the primary API call:
  - Loop over models defined in `GEMINI_MODEL`. If any succeeds, exit loop.
- Change the fallback check condition from:
  ```python
  if not success and "elysiver.h-e.top" in api_url:
  ```
  to:
  ```python
  if not success and fb_url and fb_key and fb_models:
  ```

#### [MODIFY] [.env](file:///Users/dum/google/proj/ainews/.env)

- Define the baseline default configurations:
  ```ini
  GEMINI_API_KEY=sk-4OkOspCV7Bva6xPcoNtnU3rGuafPWtV9JrHdSATTBKhMnOGH
  GEMINI_MODEL=gemini-2.5-flash,gemini-1.5-flash
  GEMINI_API_URL=https://elysiver.h-e.top/v1/chat/completions
  FALLBACK_API_URL=https://wzw.pp.ua/v1/chat/completions
  FALLBACK_API_KEY=9NJJqjmYYJSmiZYYsitQrk8AvjnF5g8rCsIeDoTWeJpS4wGu
  FALLBACK_MODELS=deepseek-ai/deepseek-v4-flash,deepseek-ai/deepseek-v4-pro
  ```

#### [MODIFY] [test_ai_analyst.py](file:///Users/dum/google/proj/ainews/tests/test_ai_analyst.py)

- Update `test_ai_generation_failover_refactored` to set/mock and clean up fallback environment variables (`FALLBACK_API_URL`, `FALLBACK_API_KEY`, `FALLBACK_MODELS`) to keep tests independent of the local `.env` values.
- Add a new unit test for model switching on the primary call to ensure multiple models are tried in order if they fail.

## Verification Plan

### Automated Tests
- Run `PYTHONPATH=. ./venv/bin/pytest` to ensure all tests continue to pass under the new configuration paradigm.
