# 国内热点事件需求挖掘工具设计方案 (Hot News Needs Miner)

本方案设计了一个基于 Python FastAPI 和本地 SQLite 数据库的热点事件收集与 AI 需求挖掘工具。该工具通过定期抓取微博热搜和知乎热榜，利用大语言模型 (LLM) 进行深度需求分析，帮助开发者/创业者挖掘出有潜在产品化可能性的用户痛点。

---

## 1. 系统架构与技术栈

本工具为一个单体全栈应用，具备开发轻量、依赖少、一键启动的特点：
*   **后端开发语言**：Python 3.10+
*   **Web 框架**：FastAPI
*   **数据库**：SQLite（本地单文件，免配置）
*   **数据抓取**：Python `requests` + `BeautifulSoup` (去重与热度解析)
*   **AI 模块**：Gemini API (或 Compatible OpenAI endpoint)，使用结构化 JSON Mode 响应
*   **前端页面**：HTML5 + 原生 CSS3 (现代暗黑毛玻璃风格) + Vanilla JavaScript
*   **页面布局**：网格卡片瀑布流 (Card Grid) + 详情弹窗 (Detail Modal)

---

## 2. 数据库设计 (SQLite)

本系统采用两张表来管理原始热点事件以及分析结果：

### 表 1：`hot_events`（热点事件表）
存储爬虫抓取到的最原始事件。通过唯一索引限制防止重复抓取。
```sql
CREATE TABLE hot_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT UNIQUE NOT NULL,         -- 事件标题，用作唯一键去重
    url TEXT,                           -- 原始链接
    platform TEXT NOT NULL,             -- 平台类型 ('weibo', 'zhihu')
    popularity INTEGER,                 -- 热度指数值
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 表 2：`need_analysis`（需求挖掘分析表）
存储 AI 针对相应热点生成的深度需求评估结果。
```sql
CREATE TABLE need_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER UNIQUE NOT NULL,   -- 外键关联 hot_events.id
    status TEXT NOT NULL,               -- 状态: 'pending' (待处理), 'analyzed' (已分析), 'low_value' (低价值过滤), 'failed' (分析失败)
    target_audience TEXT,               -- 目标用户群体描述
    pain_point TEXT,                    -- 用户的核心痛点/吐槽焦点
    product_concept TEXT,               -- AI 提出的产品/服务/工具构想
    difficulty TEXT,                    -- 开发难度评估 ('easy', 'medium', 'hard')
    value_score INTEGER,                -- 商业开发价值评分 (1-10分)
    analysis_summary TEXT,              -- 列表简短摘要 (卡片显示)
    analyzed_at DATETIME,               -- AI 处理完成的时间戳
    FOREIGN KEY (event_id) REFERENCES hot_events(id) ON DELETE CASCADE
);
```

## 3. 爬虫与抓取策略

### 数据源设计与容错机制
1.  **微博热搜**：通过抓取 `https://weibo.com/ajax/side/hotSearch` API 接口获取当前的 Top 50 实时热搜。
2.  **知乎热榜**：通过抓取 `https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total` API 接口获取当前的 Top 50 实时热榜。
3.  **容错降级 (Fallback)**：若接口由于反爬虫限制或网络故障请求失败，系统将自动回退到公开的 RSSHub 镜像源（如 `rsshub.app`），并在前端看板展示“数据源异常”的警告提示。

### 数据保留与自动清理
*   **定时清理**：后台每天定时检查数据库，自动清理超过 7 天且未被 AI 手动分析的原始热搜记录，从而控制数据库体积。
*   **永久保留**：所有已经被用户手动触发过 AI 分析的事件及其结果均永久保留。
*   **手动刷新**：提供前端 API `/api/trigger-crawl` 支持用户在页面上一键手动刷新抓取最新的数据。

---

## 4. AI 需求挖掘 Prompt 与解析策略

### 密钥管理
*   **安全存储**：API 密钥统一从本地的 [`.env`](file:///Users/dum/google/proj/ainews/.env) 文件中读取环境变量 `GEMINI_API_KEY`，符合安全开发规范。

### AI 触发模式
*   **全手动触发**：爬虫仅抓取并展示热点标题。所有的 AI 需求挖掘均不会自动批量运行，而是由用户在前端看板上点击特定事件卡片上的“🧠 AI 需求分析”按钮时单独触发，从而最大化节省 API Token 额度。

### 结构化 Prompt 定义
```
你是一名经验丰富的产品经理与天使投资分析师。
请分析以下热点事件，并评估从中是否能挖掘出特定的用户痛点，从而开发出对应的软件产品、SaaS 接口、浏览器插件或轻量级小程序。

事件标题：{title}
来源平台：{platform}

请严格按以下 JSON 格式输出，不要包含任何额外的 Markdown 格式字符：
{
  "has_value": true/false (是否具有产品化开发的价值，明星娱乐八卦、宏观国际政治等无开发价值的设为 false),
  "value_score": 1-10 之间的整数 (产品化商业开发价值评分，无开发价值的设为 1-3),
  "target_audience": "清晰精准的目标受众描述",
  "pain_point": "用户面临的深层核心痛点或吐槽点",
  "product_concept": "具体的解决方案/产品功能构想",
  "difficulty": "easy/medium/hard (开发难度评估)",
  "analysis_summary": "100字以内的卡片简短摘要"
}
```

---

## 5. Web 界面与视觉设计

页面设计为单页应用 (SPA)，并采用**方案 A（现代暗黑科技风）**以及**布局 B（网格卡片 + 详情弹窗）**。

### 过滤与展示策略
*   **高价值主视图**：前端主看板网格默认仅展示商业开发价值评分较高（得分 >= 6 分）的已分析卡片，以及未分析的原始热点。
*   **低价值过滤保护**：已被分析但得分较低（得分 < 6 分）或被 AI 标记为 `has_value = false` 的卡片默认予以隐藏。
*   **控制开关**：在左侧筛选区提供一个“显示过滤项”开关，激活后允许用户查看被 AI 淘汰归类的低价值热点，保留完整的审核权限。

### 视觉特性 (CSS)
*   **背景色**：深灰/纯黑 (`#141416` / `#1d1d1f`)
*   **卡片风格**：半透明毛玻璃效果 (`backdrop-filter: blur(10px)`)，搭配细白边框 (`border: 1px solid rgba(255,255,255,0.08)`)。
*   **评分高亮**：根据 `value_score` 的分值渲染不同的高亮颜色（例如 8分以上显示绿色 `#30d158`，6-7分显示黄色 `#ff9f0a`）。
*   **动画效果**：卡片悬浮时有平滑的向上平移及柔和阴影变化。

### 页面结构
1.  **顶部 Header**：应用标题、手动触发刷新按钮（包含爬取状态指示器）。
2.  **左侧筛选区**：平台选择（全部/微博/知乎）、开发难度（全部/简单/中等/困难）、商业价值排序（由高到低）。
3.  **主网格 Card Grid**：展示已分析的高商业价值（得分值 >= 6）的热点痛点卡片。
4.  **详情 Modal**：点击任一卡片，弹出暗色遮罩层弹窗，全面展示：
    *   原热点事件名称与原始链接。
    *   目标受众与详细痛点阐述。
    *   具体的产品构想与功能点。
    *   难度与价值双重维度的评估。

---

## 6. 验证计划

1.  **爬虫测试**：在本地运行爬虫脚本，确保能够正常发起 GET 请求并解析微博、知乎接口返回的数据。
2.  **AI 解析测试**：传入测试热搜标题，验证 Gemini API 接口的 JSON 响应解析成功率与异常处理。
3.  **前端响应式测试**：在不同尺寸（桌面、平板、手机）的屏幕上测试网格排列与 Modal 弹窗的对齐。
