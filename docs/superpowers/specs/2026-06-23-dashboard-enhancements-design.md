# 热点看板增强：日期分组 + 批量分析 + 日报生成

## 背景

当前系统每天从微博热搜、知乎热榜、知乎想法 3 个平台抓取 ~100 条热点事件，存入 SQLite。随着多日数据累积（已有 6/21、6/23 两天 187 条），面板一次性展示所有数据，查看不便。同时，单条手动分析效率低，缺乏批量处理和结果汇总能力。

## 目标

1. **日期维度切换**：以日期 Tab 为主要数据分隔手段，默认展示今天（无数据则最近一天）
2. **批量分析**：一键分析当前筛选条件下所有待分析事件，前端逐条并发调用，实时更新卡片
3. **日报生成**：将指定日期中 `value_score ≥ 6` 的已分析事件生成 Markdown 日报，后端落盘到 `docs/reports/` 并返回前端预览/下载

## 设计决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 数据分隔方式 | 日期 Tab 切换 + 垂直滚动 | 每天 ~100 条，不需要传统分页 |
| 批量分析执行方式 | 前端并发 3 路调用现有单条 API | API 限流 30 RPM 充裕；复用已有端点，无需新增后端进度管理 |
| 日报存储 | 后端生成 Markdown → 落盘 `docs/reports/` + 前端预览/下载 | 数据持久化 + 即时查看兼顾 |
| 日报内容范围 | 仅 `status=analyzed` 且 `value_score ≥ 6` | 聚焦有开发价值的热点 |
| 默认日期 | 今天，无数据则最近有数据的一天 | 最常见的使用场景 |

---

## 架构变更

### 数据流

```
用户点击日期 Tab
  → 前端请求 GET /api/events?date=2026-06-23&platform=all&status=all
  → 后端查询 SQLite，按日期+筛选条件返回事件列表
  → 前端渲染卡片（垂直滚动，无分页）

用户点击「批量分析」
  → 前端从当前已加载数据中筛选 status=pending 的事件
  → 前端并发 3 路调用 POST /api/events/{id}/analyze（复用现有 API）
  → 每条完成后更新对应卡片状态（pending → analyzed/low_value）
  → 全部完成后显示汇总 toast

用户点击「生成日报」
  → 前端请求 GET /api/report/{date}
  → 后端查询该日期 value_score ≥ 6 的事件
  → 生成 Markdown → 保存到 docs/reports/YYYY-MM-DD-daily-report.md
  → 返回 Markdown 内容给前端
  → 前端 Modal 中渲染预览 + 提供下载按钮
```

---

## 后端变更

### database.py

**修改 `get_pending_events()`** → 重命名为 `get_events_filtered(date=None, platform=None, status=None)`

```python
def get_events_filtered(date=None, platform=None, status=None):
    """
    按日期、平台、状态筛选事件。
    - date: 'YYYY-MM-DD' 格式，匹配 created_at 的日期部分
    - platform: 'weibo' / 'zhihu' / 'zhihu_pin'，None 为全部
    - status: 'pending' / 'analyzed' / 'low_value' / 'failed'，None 为全部
    返回: list[dict]
    """
```

**新增 `get_available_dates()`**

```python
def get_available_dates():
    """返回所有不重复日期列表（降序），格式 ['2026-06-23', '2026-06-21']"""
```

**新增 `get_report_data(date)`**

```python
def get_report_data(date):
    """查询指定日期 status='analyzed' 且 value_score >= 6 的事件，用于日报生成"""
```

### main.py

**修改 `GET /api/events`** — 增加查询参数 `date`、`platform`、`status`

**新增 `GET /api/dates`** — 返回可用日期列表

**新增 `GET /api/report/{date}`** — 生成日报并返回：
- 调用 `database.get_report_data(date)`
- 调用 `ai_analyst.generate_daily_report_markdown(date, events)`
- 保存到 `docs/reports/{date}-daily-report.md`
- 返回 `{"status": "success", "content": markdown_str, "file_path": "..."}`

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

### 1. [标题] (评分: 9/10)
- **平台**: 微博热搜
- **目标客群**: ...
- **核心痛点**: ...
- **产品构想**: ...
- **开发难度**: 中等
- **分析摘要**: ...

### 2. ...
```

---

## 前端变更

### index.html

- 侧边栏新增 **📅 日期** 筛选区域（动态生成日期按钮）
- 侧边栏新增 **📋 分析状态** 筛选区域
- Header 区域新增 **「⚡ 批量分析」** 按钮和 **「📄 生成日报」** 按钮
- 新增日报预览 Modal（包含 Markdown 渲染区域和下载按钮）
- 新增批量分析进度浮层（显示已完成/总数）

### app.js

**重构 `loadEvents()`**：
- 携带 `date`、`platform`、`status` 查询参数
- 页面加载时先调用 `loadDates()` 获取日期列表

**新增 `loadDates()`**：
- 请求 `GET /api/dates`
- 渲染日期按钮到侧边栏
- 默认选中今天（或最近有数据的日期）

**新增 `batchAnalyze()`**：
- 从当前已加载的 `allEvents` 中筛选 `status === 'pending'` 的事件
- 使用并发池（3 路并发）逐条调用 `POST /api/events/{id}/analyze`
- 每条完成后更新进度计数 + 重新加载卡片数据
- 全部完成后显示完成 toast

**新增 `generateReport()`**：
- 请求 `GET /api/report/{selectedDate}`
- 将返回的 Markdown 内容渲染到 Modal 中（使用简易 Markdown 解析或 `<pre>` 展示）
- 提供「下载 .md 文件」按钮

**重构筛选逻辑**：
- 日期、平台、状态、难度筛选联动
- 切换日期时重置其他筛选为默认值

### style.css

- 日期按钮样式（复用 `.filter-label` 样式体系）
- 状态筛选按钮样式
- 批量分析进度浮层样式（`.batch-progress-toast`）
- 日报 Modal 样式（`.report-modal`、`.report-content`、`.report-download-btn`）
- 新增 Header 按钮组排列样式

---

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `database.py` | MODIFY | 新增筛选查询、日期列表、日报数据查询 |
| `main.py` | MODIFY | 新增 `/api/dates`、`/api/report/{date}` 端点，修改 `/api/events` 参数 |
| `ai_analyst.py` | MODIFY | 新增 `generate_daily_report_markdown()` |
| `static/index.html` | MODIFY | 新增日期筛选、状态筛选、批量分析按钮、日报 Modal |
| `static/app.js` | MODIFY | 重构加载逻辑、新增批量分析/日报功能 |
| `static/style.css` | MODIFY | 新增日期/状态/进度/日报相关样式 |
| `docs/reports/` | NEW DIR | 日报输出目录 |

## 不在范围内

- 定时自动抓取（cron/scheduler） — 当前保持手动触发
- AI 生成日报摘要 — 日报为本地格式化，不额外调用 AI
- 数据导出 CSV/Excel — 仅 Markdown 日报
- 用户认证/权限管理
