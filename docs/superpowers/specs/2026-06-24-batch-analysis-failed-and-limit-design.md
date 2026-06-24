# 批量分析支持失败重试与数量限制设计方案

本方案旨在：
1. 允许将之前分析失败（status = 'failed'）的事件纳入批量分析，支持重新发起批量分析。
2. 根据当前的并发并发设置限制单次批量分析的数量，防止接口过载。

## 方案设计

### 1. 数据库层支持查询失败状态与状态重置

在 [database.py](file:///Users/dum/google/proj/ainews/database.py) 中：
- 修改 `get_batch_pending(date, platform=None)`，使其查询的 status 条件从原来的 `AND n.status = 'pending'` 变更为 `AND n.status IN ('pending', 'failed')`。
- 新增 `reset_event_status_to_pending(event_ids: list[int])` 辅助函数，在批量分析开始前，将选定分析的事件在数据库中的 status 统一重置为 `'pending'`，以便在批量分析运行中，如果用户刷新界面或查询时，能正确展示其为待分析状态。

### 2. 后端接口层增加数量限制

在 [main.py](file:///Users/dum/google/proj/ainews/main.py) 中：
- 定义常量 `BATCH_SIZE_LIMIT = 20`。
- 在 `/api/batch-analyze` 接口中：
  - 获取待分析列表后，记录原始待分析总数 `original_total`。
  - 使用切片限制本次处理数量：`pending = pending[:BATCH_SIZE_LIMIT]`。
  - 调用 `database.reset_event_status_to_pending(...)` 重置这些事件的状态。
  - 返回的响应数据增加 `original_total` 和 `limit` 字段，供前端做更友好的提示：
    ```json
    {
      "status": "started",
      "total": 20,
      "original_total": 25,
      "limit": 20
    }
    ```

### 3. 前端提示优化

在 [static/app.js](file:///Users/dum/google/proj/ainews/static/app.js) 中：
- 在 `batchAnalyze` 启动成功后，判断 `data.original_total > data.limit`。
- 若超出限制，弹窗提示用户：“提示：当前共有 ${data.original_total} 条待分析/失败的事件。由于并发限制，本次批量分析仅处理前 ${data.limit} 条，其余事件可在完成后再次发起分析。”

### 4. AI 模型调用容灾（Failover）

在 [ai_analyst.py](file:///Users/dum/google/proj/ainews/ai_analyst.py) 中：
- 抽取通用的 API 请求函数 `_call_openai_compatible_api(url, key, model, prompt, max_retries)` 以消除代码冗余。
- 修改 `analyze_hot_topic(title, platform)` 函数：
  1. 首先尝试主调用（`https://elysiver.h-e.top`，重试最多 3 次）。
  2. 如果主调用失败（异常或非 2xx 响应），且主 URL 包含 `elysiver.h-e.top`，则进行容灾切换：
     - **备用配置优先读取环境变量**（`FALLBACK_API_URL`, `FALLBACK_API_KEY`），若不存在则使用指定的硬编码默认值（`https://wzw.pp.ua/v1/chat/completions` 和对应的 Key）。
     - 尝试使用第一个备用模型 `deepseek-ai/deepseek-v4-flash`（最大重试 1 次）。
     - 如果第一备用模型失败，则尝试第二个备用模型 `deepseek-ai/deepseek-v4-pro`（最大重试 1 次）。
  3. 任一阶段成功即返回结果，彻底失败则返回带有错误详情的统一格式字典。

---

## 验证方案

### 自动化测试
1. 修改 `tests/test_database.py`，测试 `get_batch_pending` 能同时查出 `pending` 和 `failed` 的事件。
2. 增加/修改 `tests/test_main.py`，测试当待分析数量超过 `BATCH_SIZE_LIMIT` 时，只取出前 20 条进行分析，且返回正确的 `original_total` 和 `limit`。
3. 增加 `tests/test_ai_analyst.py` 测试，模拟主调用 `https://elysiver.h-e.top` 失败的情况，并验证调用是否成功 failover 到 `https://wzw.pp.ua` 并尝试备用 DeepSeek 模型。

