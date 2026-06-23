# 热点看板增强：日期分组 + 批量分析 + 日报生成

## 背景

当前系统每天从微博热搜、知乎热榜、知乎想法 3 个平台抓取 ~100 条热点事件，存入 SQLite。随着多日数据累积（已有 6/21、6/23 两天 187 条），面板一次性展示所有数据，查看不便。同时，单条手动分析效率低，缺乏批量处理和结果汇总能力。

## 目标

1. **日期维度切换**：以日期 Tab 为主要数据分隔手段，默认展示今天（无数据则最近一天）
2. **批量分析**：一键分析当前日期+平台下所有待分析事件，后端 BackgroundTasks 驱动（5 路并发），前端轮询进度
3. **日报生成**：将指定日期中 `value_score ≥ 6` 的已分析事件生成 Markdown 日报，后端落盘到 `docs/reports/` 并返回 HTML 供前端预览/下载

## 设计决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 数据分隔方式 | 日期 Tab 切换 + 垂直滚动 | 每天 ~100 条，不需要传统分页 |
| 批量分析执行方式 | 后端 BackgroundTasks + 5 路并发 + 进度查询端点 | 可靠性优先，关闭浏览器不影响后台任务；API 限流 30 RPM，5 路并发安全 |
| 批量分析范围 | 当前选中日期 + 平台的待分析事件 | 和用户看到的页面数据保持一致 |
| 批量分析容错 | 记录失败项，进度 API 返回汇总 | 部分失败不阻断整体流程 |
| 批量分析防重复 | 后端全局锁 + 前端禁用按钮 | 防止并发任务冲突 |
| 日报存储 | 后端生成 Markdown → 落盘 `docs/reports/` + 前端预览/下载 | 数据持久化 + 即时查看兼顾 |
| 日报 API 方法 | `POST /api/report/{date}` | 有文件写入副作用，POST 更符合 REST 语义 |
| 日报内容范围 | 仅 `status=analyzed` 且 `value_score ≥ 6` | 聚焦有开发价值的热点 |
| Markdown 渲染 | 后端 Python `markdown` 库转 HTML 返回 | 零前端依赖，渲染质量有保障 |
| 默认日期 | 今天，无数据则最近有数据的一天 | 最常见的使用场景 |
| 时区处理 | SQL 查询中 `datetime(created_at, '+8 hours')` | created_at 存 UTC，查询时转 UTC+8 再取日期 |
| 筛选模型 | 统一后端筛选（日期+平台+状态+难度） | 架构一致性，避免前后端混合过滤的维护成本 |
| 低价值 Toggle | 保留，但仅在状态筛选="全部"时生效 | 避免与状态筛选功能冲突，减少用户困惑 |

---

## 架构变更

### 数据流

```
用户点击日期 Tab
  → 前端请求 GET /api/events?date=2026-06-23&platform=all&status=all&difficulty=all&show_low_value=false
  → 后端查询 SQLite（created_at 做 UTC+8 转换后按日期匹配），按筛选条件返回事件列表
  → 前端渲染卡片（垂直滚动，无分页）

用户点击「批量分析」
  → 前端请求 POST /api/batch-analyze {date: "2026-06-23", platform: "all"}
  → 后端检查全局锁：已有任务运行则拒绝（409 Conflict）
  → 后端查询匹配的待分析事件，启动 BackgroundTasks（5 路并发 ThreadPoolExecutor）
  → 前端开始轮询 GET /api/batch-analyze/status（每 2 秒）
  → 后端返回 {running: true, total: 50, completed: 30, failed: 2, failed_titles: [...]}
  → 前端更新进度浮层
  → 任务完成后前端重新 loadEvents() 刷新视图

用户点击「生成日报」
  → 前端请求 POST /api/report/{date}
  → 后端查询该日期 value_score ≥ 6 的已分析事件
  → 生成 Markdown → 保存到 docs/reports/YYYY-MM-DD-daily-report.md
  → Python markdown 库转 HTML
  → 返回 {status, markdown, html, file_path}
  → 前端 Modal 中 innerHTML 渲染 HTML + 提供下载 .md 按钮
```

---

## 后端变更

### database.py

**重构 `get_pending_events()`** → 重命名为 `get_events_filtered(date=None, platform=None, status=None, difficulty=None, show_low_value=True)`

```python
def get_events_filtered(date=None, platform=None, status=None, difficulty=None, show_low_value=True):
    """
    按日期、平台、状态、难度筛选事件。
    - date: 'YYYY-MM-DD' 格式，匹配 datetime(created_at, '+8 hours') 的日期部分
    - platform: 'weibo' / 'zhihu' / 'zhihu_pin'，None 为全部
    - status: 'pending' / 'analyzed' / 'low_value' / 'failed'，None 为全部
    - difficulty: 'easy' / 'medium' / 'hard'，None 为全部
    - show_low_value: 当 status=None 时，是否包含 low_value 事件
    返回: list[dict]
    """
```

**新增 `get_available_dates()`**

```python
def get_available_dates():
    """
    返回所有不重复日期列表（降序），使用 UTC+8 转换。
    SELECT DISTINCT date(datetime(created_at, '+8 hours')) as local_date
    FROM hot_events ORDER BY local_date DESC
    返回: ['2026-06-23', '2026-06-21']
    """
```

**新增 `get_report_data(date)`**

```python
def get_report_data(date):
    """
    查询指定日期（UTC+8）status='analyzed' 且 value_score >= 6 的事件。
    按 value_score DESC 排序。返回完整字段用于日报生成。
    """
```

**新增 `get_batch_pending(date, platform=None)`**

```python
def get_batch_pending(date, platform=None):
    """
    查询指定日期（UTC+8）+ 平台下所有 status='pending' 的事件。
    返回 [(id, title, platform), ...]
    """
```

### main.py

**修改 `GET /api/events`** — 增加查询参数：
- `date: str = None`
- `platform: str = None`
- `status: str = None`
- `difficulty: str = None`
- `show_low_value: bool = True`

**新增 `GET /api/dates`** — 返回 `{"dates": [...]}`

**新增 `POST /api/batch-analyze`** — 接收 `{date, platform}` body：
- 检查全局锁 `batch_state["running"]`，已运行返回 409
- 查询待分析事件列表
- 用 `threading.Thread` + `concurrent.futures.ThreadPoolExecutor(max_workers=5)` 在后台执行
- 立即返回 `{"status": "started", "total": N}`

**新增 `GET /api/batch-analyze/status`** — 返回进度：
```json
{
  "running": true,
  "total": 50,
  "completed": 30,
  "failed": 2,
  "failed_titles": ["事件A", "事件B"]
}
```

**新增 `POST /api/report/{date}`** — 生成日报：
- 调用 `database.get_report_data(date)`
- 调用 `ai_analyst.generate_daily_report_markdown(date, events)` 获取 Markdown
- 保存到 `docs/reports/{date}-daily-report.md`
- 用 Python `markdown` 库转 HTML
- 返回 `{"status": "success", "markdown": md_str, "html": html_str, "file_path": "..."}`

### ai_analyst.py

**新增 `generate_daily_report_markdown(date, events)`**

纯本地字符串格式化，不调用 AI API。生成结构：

```markdown
# 📊 热点需求日报 — 2026-06-23

## 概要
- 高价值热点数: X 条
- 平台分布: 微博 X 条 / 知乎 X 条 / 知乎想法 X 条
- 最高评分: X 分

## 🔥 高价值热点详情

### 1. [标题] (⭐ 评分: 9/10)
- **来源平台**: 微博热搜
- **目标客群**: ...
- **核心痛点**: ...
- **产品构想**: ...
- **开发难度**: 中等
- **分析摘要**: ...

### 2. ...

---
*报告生成时间: 2026-06-23 23:00:00*
```

---

## 前端变更

### index.html

- 侧边栏新增 **📅 日期** 筛选区域（`#date-filters`，由 JS 动态填充）
- 侧边栏新增 **📋 分析状态** 筛选区域（`#status-filters`，全部/待分析/已分析/低价值/失败）
- 低价值 toggle 保留，但当状态筛选不为"全部"时自动禁用（灰色）
- Header 新增 **「⚡ 批量分析」** 按钮（`#batch-analyze-btn`）和 **「📄 生成日报」** 按钮（`#generate-report-btn`）
- 新增批量分析进度浮层（`#batch-progress`，底部居中固定定位）
- 新增日报预览 Modal（`#report-modal`，含 HTML 渲染区 + Markdown 下载按钮）

### app.js

**新增全局状态：**
```javascript
let selectedDate = null;
let selectedStatus = 'all';
let selectedDifficulty = 'all';
let availableDates = [];
```

**新增 `loadDates()`**：请求 `GET /api/dates`，渲染日期按钮，自动选中今天或最近一天。

**重构 `loadEvents()`**：携带所有筛选参数请求后端，不再做前端过滤。

**重构 `renderGrid()`**：移除前端过滤逻辑，直接渲染后端返回的数据。

**新增 `batchAnalyze()`**：POST 请求启动批量分析，每 2 秒轮询进度，完成后刷新。

**新增 `generateReport()`**：POST 请求生成日报，Modal 中 innerHTML 渲染 HTML，提供 Blob 下载。

**新增筛选器绑定**：日期、状态、难度切换时调用 `loadEvents()`。Toggle 在 status≠all 时禁用。

### style.css

- 日期筛选按钮样式（复用 `.filter-label`）
- 状态筛选按钮的各状态配色
- 批量分析进度浮层（`.batch-progress-toast`，固定底部居中，glassmorphism）
- 进度条（`.progress-bar` + `.progress-fill`）
- 日报预览 Modal（`.report-modal`，复用 `.modal-overlay` 基础）
- 日报内容区渲染样式（标题、表格、列表等 HTML 元素的暗色主题适配）
- 下载按钮样式
- Toggle 禁用态样式

---

## 新增依赖

- Python `markdown` 库（需要 `pip install markdown` 并更新 `requirements.txt`）

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `database.py` | MODIFY | 重构查询方法 + 新增 4 个方法 |
| `main.py` | MODIFY | 修改 1 个端点 + 新增 4 个端点 |
| `ai_analyst.py` | MODIFY | 新增 `generate_daily_report_markdown()` |
| `static/index.html` | MODIFY | 新增日期/状态筛选、按钮、浮层、Modal |
| `static/app.js` | MODIFY | 重构加载/筛选逻辑，新增批量分析/日报功能 |
| `static/style.css` | MODIFY | 新增所有相关样式 |
| `requirements.txt` | MODIFY | 添加 `markdown` 依赖 |
| `docs/reports/` | NEW DIR | 日报输出目录 |

## 不在范围内

- 定时自动抓取（cron/scheduler） — 当前保持手动触发
- AI 生成日报摘要 — 日报为本地格式化，不额外调用 AI
- 数据导出 CSV/Excel — 仅 Markdown 日报
- 用户认证/权限管理
