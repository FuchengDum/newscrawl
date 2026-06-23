# 国内热点事件需求挖掘工具 (Hot News Needs Miner) 执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收集微博热搜与知乎热榜事件，并通过 Gemini AI 深入挖掘用户的痛点及潜在产品商机，最终以暗黑毛玻璃风格的可视化看板展现。

**Architecture:** 本应用采用 Python FastAPI 构建轻量后端服务，结合 SQLite 本地单文件数据库持久化数据，定时/手动抓取微博/知乎热点，并由用户手动触发 Gemini AI 的 JSON Mode 进行需求抽取。前端采用原生的 HTML+CSS+JS 实现卡片网格与模态框交互。

**Tech Stack:** Python, FastAPI, SQLite, Gemini API (google-generativeai), HTML5, Vanilla CSS3, Vanilla JS.

## Global Constraints
*   项目需使用 Python 3.10+。
*   API 密钥从本地的 `.env` 文件读取，不硬编码。
*   对于失败的接口，自动降级至公网 RSSHub 镜像源并展示警告。
*   默认在前端隐藏低商业价值（分值 < 6）卡片，支持“显示过滤项”开关切换。
*   每次抓取完自动定时删除 7 天前未被分析的原始事件。

---

## 计划文件结构规划

```
/Users/dum/google/proj/ainews/
├── .env                              # 本地环境变量配置文件
├── requirements.txt                  # 后端依赖配置
├── database.py                       # 数据库连接、表定义及操作类
├── crawler.py                        # 微博/知乎及 RSSHub 降级爬虫
├── ai_analyst.py                     # Gemini AI 分析与 JSON Mode 解析
├── main.py                           # FastAPI 后端服务及 API 路由定义
├── static/                           # 前端静态资源目录
│   ├── index.html                    # 网格卡片及弹窗结构
│   ├── style.css                     # 暗黑毛玻璃 CSS
│   └── app.js                        # 前端数据交互、分析触发及过滤逻辑
└── tests/                            # 自动化测试目录
    ├── test_crawler.py               # 爬虫单元测试
    ├── test_ai_analyst.py            # AI分析单元测试
    └── test_database.py              # 数据库操作单元测试
```

---

## 任务详情

### Task 1: 依赖配置与 SQLite 数据库搭建

**Files:**
*   Create: `requirements.txt`
*   Create: `database.py`
*   Create: `tests/test_database.py`

**Interfaces:**
*   Consumes: None
*   Produces: `get_db_connection()`, `init_db()`, `save_hot_event(title, url, platform, popularity)`, `get_pending_events()`, `update_analysis(event_id, analysis_json)`, `delete_old_unanalyzed_events()`

- [ ] **Step 1: 创建 requirements.txt 配置文件**
    写入 Python 后端依赖库：
    ```text
    fastapi>=0.100.0
    uvicorn>=0.22.0
    requests>=2.31.0
    beautifulsoup4>=4.12.2
    lxml>=4.9.0
    google-generativeai>=0.3.0
    python-dotenv>=1.0.0
    pytest>=7.3.0
    ```

- [ ] **Step 2: 编写数据库逻辑 database.py**
    ```python
    import sqlite3
    from datetime import datetime, timedelta

    DB_FILE = "ainews.db"

    def get_db_connection():
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db():
        with get_db_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS hot_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT UNIQUE NOT NULL,
                url TEXT,
                platform TEXT NOT NULL,
                popularity INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS need_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER UNIQUE NOT NULL,
                status TEXT NOT NULL, -- 'pending', 'analyzed', 'low_value', 'failed'
                target_audience TEXT,
                pain_point TEXT,
                product_concept TEXT,
                difficulty TEXT,
                value_score INTEGER,
                analysis_summary TEXT,
                analyzed_at DATETIME,
                FOREIGN KEY (event_id) REFERENCES hot_events(id) ON DELETE CASCADE
            );
            """)
            conn.commit()

    def save_hot_event(title, url, platform, popularity):
        with get_db_connection() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO hot_events (title, url, platform, popularity) VALUES (?, ?, ?, ?)",
                    (title, url, platform, popularity)
                )
                event_id = cursor.lastrowid
                conn.execute(
                    "INSERT INTO need_analysis (event_id, status) VALUES (?, 'pending')",
                    (event_id,)
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # 标题已存在，跳过插入
                return False

    def get_pending_events():
        with get_db_connection() as conn:
            rows = conn.execute("""
                SELECT h.id, h.title, h.url, h.platform, h.popularity, n.status 
                FROM hot_events h
                JOIN need_analysis n ON h.id = n.event_id
                ORDER BY h.popularity DESC
            """).fetchall()
            return [dict(r) for r in rows]

    def update_analysis(event_id, a):
        # a 是字典，包含 has_value, value_score, target_audience, pain_point, product_concept, difficulty, analysis_summary
        status = "analyzed" if a.get("has_value") and a.get("value_score", 0) >= 6 else "low_value"
        with get_db_connection() as conn:
            conn.execute("""
                UPDATE need_analysis SET
                    status = ?,
                    target_audience = ?,
                    pain_point = ?,
                    product_concept = ?,
                    difficulty = ?,
                    value_score = ?,
                    analysis_summary = ?,
                    analyzed_at = ?
                WHERE event_id = ?
            """, (
                status,
                a.get("target_audience"),
                a.get("pain_point"),
                a.get("product_concept"),
                a.get("difficulty"),
                a.get("value_score"),
                a.get("analysis_summary"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                event_id
            ))
            conn.commit()

    def delete_old_unanalyzed_events():
        limit_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        with get_db_connection() as conn:
            # 删除未被分析或标记为低价值且超过 7 天的原始事件
            conn.execute("""
                DELETE FROM hot_events 
                WHERE created_at < ? AND id IN (
                    SELECT event_id FROM need_analysis WHERE status IN ('pending', 'low_value', 'failed')
                )
            """, (limit_date,))
            conn.commit()
    ```

- [ ] **Step 3: 编写数据库单元测试 tests/test_database.py**
    ```python
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
    ```

- [ ] **Step 4: 运行数据库测试**
    运行：`pytest tests/test_database.py -v`
    预期：PASS

---

### Task 2: 爬虫与 RSSHub 降级机制开发

**Files:**
*   Create: `crawler.py`
*   Create: `tests/test_crawler.py`

**Interfaces:**
*   Consumes: `save_hot_event(title, url, platform, popularity)`
*   Produces: `fetch_weibo_hot()`, `fetch_zhihu_hot()`, `crawl_and_save_all()`

- [ ] **Step 1: 编写爬虫脚本 crawler.py**
    ```python
    import urllib.request
    import urllib.error
    import http.cookiejar
    import json
    from bs4 import BeautifulSoup
    import database

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 公共 RSSHub 镜像列表，用于降级和规避限制
    RSSHUB_MIRRORS = [
        "https://rsshub.rssforever.com",
        "https://hub.slarker.me",
        "https://rsshub.app"
    ]

    def fetch_weibo_hot():
        # 微博 API 直接请求会返回 403，需要使用 CookieJar 模拟访问主页获取客体会话 Token 后再请求
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        opener.addheaders = [
            ("User-Agent", HEADERS["User-Agent"]),
            ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
            ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8")
        ]
        
        # 1. 握手访问主页获取 Cookie
        try:
            opener.open("https://weibo.com/", timeout=8)
        except Exception:
            # 握手失败，直接走 RSSHub 降级
            return fetch_weibo_rss_fallback()

        # 2. 带 Cookie 请求 AJAX 接口
        api_headers = {
            "User-Agent": HEADERS["User-Agent"],
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://weibo.com/",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        try:
            req = urllib.request.Request("https://weibo.com/ajax/side/hotSearch", headers=api_headers)
            with opener.open(req, timeout=8) as res:
                data = json.loads(res.read().decode('utf-8'))
                realtime = data.get("data", {}).get("realtime", [])
                results = []
                for item in realtime[:50]:
                    title = item.get("word", "")
                    if not title:
                        continue
                    url_link = f"https://s.weibo.com/weibo?q={title}"
                    popularity = item.get("num", 0)
                    results.append({"title": title, "url": url_link, "platform": "weibo", "popularity": popularity})
                return results, False  # 抓取成功，未启用降级
        except Exception:
            return fetch_weibo_rss_fallback()

    def fetch_weibo_rss_fallback():
        # 遍历 RSSHub 镜像尝试抓取
        for mirror in RSSHUB_MIRRORS:
            rss_url = f"{mirror}/weibo/search/hot/fulltext"
            try:
                req = urllib.request.Request(rss_url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=8) as res:
                    soup = BeautifulSoup(res.read(), "xml")
                    items = soup.find_all("item")
                    results = []
                    for idx, item in enumerate(items[:50]):
                        title = item.title.text if item.title else "微博热搜项"
                        link = item.link.text if item.link else "https://s.weibo.com"
                        results.append({"title": title, "url": link, "platform": "weibo", "popularity": 100000 - idx})
                    if results:
                        return results, True  # 降级成功
            except Exception:
                continue
        return [], True

    def fetch_zhihu_hot():
        # 知乎 API (api.zhihu.com) 存在严苛的 IP 访问流控，直接在本地请求频繁报错 403/401。
        # 因此，我们优先从公共 RSSHub 镜像中读取（镜像自带缓存，极不容易被封），如果失败再尝试直接请求 API 降级。
        for mirror in RSSHUB_MIRRORS:
            rss_url = f"{mirror}/zhihu/hot"
            try:
                req = urllib.request.Request(rss_url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=8) as res:
                    soup = BeautifulSoup(res.read(), "xml")
                    items = soup.find_all("item")
                    results = []
                    for idx, item in enumerate(items[:50]):
                        title = item.title.text if item.title else "知乎热点项"
                        link = item.link.text if item.link else "https://www.zhihu.com"
                        results.append({"title": title, "url": link, "platform": "zhihu", "popularity": 500000 - idx * 10000})
                    if results:
                        return results, False  # 走公共镜像缓存也是常规且推荐的方案
            except Exception:
                continue
        
        # 如果镜像全部失败，最后尝试直接调用 client API（有 403 风险）
        try:
            req = urllib.request.Request("https://api.zhihu.com/topstory/hot-lists/total?limit=50", headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as res:
                data = json.loads(res.read().decode('utf-8'))
                items = data.get("data", [])
                results = []
                for item in items[:50]:
                    target = item.get("target", {})
                    title = target.get("title", "")
                    if not title:
                        continue
                    id_num = target.get("id", "")
                    url_link = f"https://www.zhihu.com/question/{id_num}" if id_num else "https://www.zhihu.com"
                    metrics = item.get("detail_text", "0")
                    try:
                        popularity = int(metrics.replace(" 万热度", "").replace("万", "").strip()) * 10000
                    except ValueError:
                        popularity = 500000
                    results.append({"title": title, "url": url_link, "platform": "zhihu", "popularity": popularity})
                return results, True  # 标记为降级/异常源
        except Exception:
            return [], True

    def fetch_zhihu_pins():
        # 获取知乎想法（24小时新闻汇总）
        for mirror in RSSHUB_MIRRORS:
            rss_url = f"{mirror}/zhihu/pin/daily"
            try:
                req = urllib.request.Request(rss_url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=8) as res:
                    soup = BeautifulSoup(res.read(), "xml")
                    items = soup.find_all("item")
                    results = []
                    for idx, item in enumerate(items[:50]):
                        title = item.title.text if item.title else "知乎想法项"
                        link = item.link.text if item.link else "https://www.zhihu.com"
                        results.append({"title": title, "url": link, "platform": "zhihu_pin", "popularity": 300000 - idx * 5000})
                    if results:
                        return results, False  # 正常获取
            except Exception:
                continue
        return [], True  # 所有镜像失败，返回异常

    def crawl_and_save_all():
        database.init_db()
        weibo_list, weibo_fallback = fetch_weibo_hot()
        zhihu_list, zhihu_fallback = fetch_zhihu_hot()
        pin_list, pin_fallback = fetch_zhihu_pins()
        
        weibo_count = 0
        for item in weibo_list:
            if database.save_hot_event(item["title"], item["url"], item["platform"], item["popularity"]):
                weibo_count += 1
                
        zhihu_count = 0
        for item in zhihu_list:
            if database.save_hot_event(item["title"], item["url"], item["platform"], item["popularity"]):
                zhihu_count += 1
                
        pin_count = 0
        for item in pin_list:
            if database.save_hot_event(item["title"], item["url"], item["platform"], item["popularity"]):
                pin_count += 1
                
        return {
            "weibo_inserted": weibo_count,
            "weibo_fallback": weibo_fallback,
            "zhihu_inserted": zhihu_count,
            "zhihu_fallback": zhihu_fallback,
            "zhihu_pin_inserted": pin_count,
            "zhihu_pin_fallback": pin_fallback
        }
    ```

- [ ] **Step 2: 编写爬虫模块测试 tests/test_crawler.py**
    ```python
    import crawler
    import database
    import os

    def setup_module(module):
        database.DB_FILE = "test_ainews.db"
        database.init_db()

    def teardown_module(module):
        if os.path.exists("test_ainews.db"):
            os.remove("test_ainews.db")

    def test_weibo_crawling():
        # 这里进行实际的网络请求，测试微博API解析
        data, fallback = crawler.fetch_weibo_hot()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "title" in data[0]
            assert data[0]["platform"] == "weibo"

    def test_crawl_and_save():
        summary = crawler.crawl_and_save_all()
        assert "weibo_inserted" in summary
        assert "zhihu_inserted" in summary
        assert "zhihu_pin_inserted" in summary
    ```

- [ ] **Step 3: 运行爬虫单元测试**
    运行：`pytest tests/test_crawler.py -v`
    Expected: PASS

---

### Task 3: AI 分析与 Gemini API 对接开发

**Files:**
*   Create: `.env`
*   Create: `ai_analyst.py`
*   Create: `tests/test_ai_analyst.py`

**Interfaces:**
*   Consumes: `update_analysis(event_id, analysis_json)`
*   Produces: `analyze_hot_topic(title, platform)`, `trigger_event_analysis(event_id, title, platform)`

- [ ] **Step 1: 创建配置文件 .env**
    写入您的 Gemini 密钥，例如：
    ```env
    GEMINI_API_KEY=your_actual_gemini_api_key_here
    ```

- [ ] **Step 2: 编写 AI 分析核心逻辑 ai_analyst.py**
    ```python
    import os
    import json
    import google.generativeai as genai
    from dotenv import load_dotenv
    import database

    load_dotenv()

    # 初始化配置
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)

    def analyze_hot_topic(title, platform):
        if not api_key:
            return {
                "has_value": False,
                "value_score": 1,
                "target_audience": "未配置API密钥",
                "pain_point": "请检查环境变量或.env文件中的GEMINI_API_KEY",
                "product_concept": "未配置密钥",
                "difficulty": "easy",
                "analysis_summary": "请先配置密钥"
            }
            
        prompt = f"""
        你是一名经验丰富的产品经理与天使投资分析师。
        请分析以下热点事件，并评估从中是否能挖掘出特定的用户痛点，从而开发出对应的软件产品、SaaS 接口、浏览器插件或轻量级小程序。

        事件标题：{title}
        来源平台：{platform}

        请严格按以下 JSON 格式输出，不要包含任何额外的 Markdown 格式字符：
        {{
          "has_value": true/false (是否具有产品化开发的价值，明星娱乐八卦、宏观国际政治等无开发价值的设为 false),
          "value_score": 1-10 之间的整数 (产品化商业开发价值评分，无开发价值的设为 1-3),
          "target_audience": "清晰精准的目标受众描述",
          "pain_point": "用户面临的深层核心痛点或吐槽点",
          "product_concept": "具体的解决方案/产品功能构想",
          "difficulty": "easy/medium/hard (开发难度评估)",
          "analysis_summary": "100字以内的卡片简短摘要"
        }}
        """
        
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            analysis = json.loads(response.text.strip())
            return analysis
        except Exception as e:
            return {
                "has_value": False,
                "value_score": 1,
                "target_audience": "错误",
                "pain_point": f"Gemini API 报错: {str(e)}",
                "product_concept": "分析失败",
                "difficulty": "easy",
                "analysis_summary": "API调用异常"
            }

    def trigger_event_analysis(event_id, title, platform):
        # 抓取原始信息后调用 AI 并回填数据库
        analysis = analyze_hot_topic(title, platform)
        database.update_analysis(event_id, analysis)
        return analysis
    ```

- [ ] **Step 3: 编写 AI 分析单元测试 tests/test_ai_analyst.py**
    ```python
    import ai_analyst
    from dotenv import load_dotenv
    import os

    def test_mock_analysis_without_key():
        # 测试在未提供 API 密钥时能正确回退并报错
        os.environ["GEMINI_API_KEY"] = ""
        ai_analyst.api_key = ""
        res = ai_analyst.analyze_hot_topic("加班报销难", "weibo")
        assert res["has_value"] is False
        assert "密钥" in res["pain_point"]

    def test_ai_generation_output():
        # 如果当前环境有可用的 KEY，进行真实集成测试
        load_dotenv()
        real_key = os.getenv("GEMINI_API_KEY")
        if real_key:
            ai_analyst.api_key = real_key
            import google.generativeai as genai
            genai.configure(api_key=real_key)
            
            res = ai_analyst.analyze_hot_topic("程序员加班脱发问题", "zhihu")
            assert "value_score" in res
            assert isinstance(res["value_score"], int)
            assert "target_audience" in res
    ```

- [ ] **Step 4: 运行 AI 分析测试**
    运行：`pytest tests/test_ai_analyst.py -v`
    Expected: PASS

---

### Task 4: FastAPI 服务及 API 路由定义

**Files:**
*   Create: `main.py`

**Interfaces:**
*   Consumes: `get_pending_events()`, `crawl_and_save_all()`, `trigger_event_analysis(event_id, title, platform)`, `delete_old_unanalyzed_events()`
*   Produces: FastAPI server hosting `/api/events`, `/api/trigger-crawl`, `/api/events/{id}/analyze`

- [ ] **Step 1: 编写应用入口与路由 main.py**
    ```python
    import os
    from fastapi import FastAPI, BackgroundTasks, HTTPException
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    import database
    import crawler
    import ai_analyst

    app = FastAPI(title="Hot News Needs Miner")

    # 启动时初始化数据库，并进行自动数据清理
    @app.on_event("startup")
    def startup_event():
        database.init_db()
        database.delete_old_unanalyzed_events()

    @app.get("/api/events")
    def get_events():
        # 获取所有事件，包括分析结果与状态
        try:
            return database.get_pending_events()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/trigger-crawl")
    def trigger_crawl(background_tasks: BackgroundTasks):
        # 触发后台抓取任务
        try:
            summary = crawler.crawl_and_save_all()
            # 顺便运行过期数据清理
            database.delete_old_unanalyzed_events()
            return {"status": "success", "summary": summary}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/events/{event_id}/analyze")
    def analyze_event(event_id: int, payload: dict):
        title = payload.get("title")
        platform = payload.get("platform")
        if not title or not platform:
            raise HTTPException(status_code=400, detail="Missing title or platform")
        try:
            analysis = ai_analyst.trigger_event_analysis(event_id, title, platform)
            return {"status": "success", "analysis": analysis}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 挂载前端静态文件目录
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)

    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    ```

- [ ] **Step 2: 本地运行并验证接口响应**
    运行：`uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
    等待服务启动，并在后台检查 `/api/events` 路由是否能正常访问（应返回空列表 `[]`）。

---

### Task 5: 现代暗黑科技风网格看板前端设计

**Files:**
*   Create: `static/index.html`
*   Create: `static/style.css`
*   Create: `static/app.js`

**Interfaces:**
*   Consumes: `/api/events` (GET), `/api/trigger-crawl` (POST), `/api/events/{id}/analyze` (POST)
*   Produces: 完整的浏览器端可视化看板

- [ ] **Step 1: 创建静态首页页面 static/index.html**
    ```html
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🔥 国内热点需求挖掘看板</title>
        <link rel="stylesheet" href="style.css">
    </head>
    <body>
        <header class="dashboard-header">
            <div class="logo-area">
                <h1>🔥 舆情热点需求捕手</h1>
                <span class="tagline">实时挖掘微博、知乎热点背后的商业产品契机</span>
            </div>
            <div class="controls-area">
                <span id="warning-badge" class="warning-badge hide">⚠️ 核心API流控，已启用RSSHub降级数据</span>
                <button id="refresh-btn" class="action-btn">🔄 刷新抓取热点</button>
            </div>
        </header>

        <div class="main-layout">
            <aside class="sidebar">
                <div class="filter-section">
                    <h3>📊 来源平台</h3>
                    <div class="filter-options">
                        <label class="filter-label active" data-platform="all">全部</label>
                        <label class="filter-label" data-platform="weibo">微博热搜</label>
                        <label class="filter-label" data-platform="zhihu">知乎热榜</label>
                    </div>
                </div>

                <div class="filter-section">
                    <h3>🛠️ 开发难度</h3>
                    <div class="filter-options">
                        <label class="filter-label active" data-difficulty="all">全部</label>
                        <label class="filter-label" data-difficulty="easy">简单 (插件/脚本)</label>
                        <label class="filter-label" data-difficulty="medium">中等 (小程序/网站)</label>
                        <label class="filter-label" data-difficulty="hard">困难 (深研/AI/大数据)</label>
                    </div>
                </div>

                <div class="filter-section toggle-wrapper">
                    <label class="switch-container">
                        <input type="checkbox" id="show-low-value-toggle">
                        <span class="slider"></span>
                    </label>
                    <span class="toggle-text">显示 AI 低价值过滤项</span>
                </div>
            </aside>

            <main class="content-grid-wrapper">
                <div id="cards-grid" class="cards-grid">
                    <!-- 卡片由 JavaScript 动态生成 -->
                </div>
            </main>
        </div>

        <!-- 详情 Modal -->
        <div id="detail-modal" class="modal-overlay hide">
            <div class="modal-card">
                <div class="modal-header">
                    <span id="modal-platform" class="modal-platform">微博热搜</span>
                    <button id="close-modal-btn" class="close-btn">&times;</button>
                </div>
                <div class="modal-body">
                    <h2 id="modal-title">热点事件标题加载中...</h2>
                    <a id="modal-url" href="#" target="_blank" class="source-link">🔗 查看原始探讨链接</a>
                    
                    <hr class="modal-divider">

                    <div class="analysis-box">
                        <div class="analysis-item">
                            <span class="label">🎯 目标客群 (Target Audience)</span>
                            <p id="modal-audience">加载中...</p>
                        </div>
                        <div class="analysis-item">
                            <span class="label">😭 核心痛点 (User Pain Point)</span>
                            <p id="modal-pain">加载中...</p>
                        </div>
                        <div class="analysis-item">
                            <span class="label">💡 产品构想 (Product Concept)</span>
                            <p id="modal-concept">加载中...</p>
                        </div>
                    </div>

                    <div class="analysis-footer">
                        <div class="footer-stat">
                            <span class="label">开发难度</span>
                            <span id="modal-difficulty" class="val">中等</span>
                        </div>
                        <div class="footer-stat">
                            <span class="label">商业开发价值评分</span>
                            <span id="modal-score" class="val score-high">9.5 分</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script src="app.js"></script>
    </body>
    </html>
    ```

- [ ] **Step 2: 编写毛玻璃暗黑 CSS 样式 static/style.css**
    ```css
    :root {
        --bg-main: #0c0c0e;
        --bg-sidebar: #141416;
        --border-color: rgba(255, 255, 255, 0.08);
        --text-main: #f5f5f7;
        --text-sub: #86868b;
        --accent-blue: #0a84ff;
        --accent-green: #30d158;
        --accent-orange: #ff9f0a;
        --accent-red: #ff453a;
        --card-bg: rgba(255, 255, 255, 0.03);
        --card-hover: rgba(255, 255, 255, 0.07);
    }

    * {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }

    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background-color: var(--bg-main);
        color: var(--text-main);
        min-height: 100vh;
        display: flex;
        flex-direction: column;
    }

    /* Header */
    .dashboard-header {
        background-color: var(--bg-sidebar);
        border-bottom: 1px solid var(--border-color);
        padding: 1rem 2rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .logo-area h1 {
        font-size: 1.4rem;
        font-weight: 700;
        letter-spacing: -0.02em;
    }

    .tagline {
        font-size: 0.8rem;
        color: var(--text-sub);
    }

    .warning-badge {
        background-color: rgba(255, 159, 10, 0.15);
        color: var(--accent-orange);
        border: 1px solid rgba(255, 159, 10, 0.3);
        font-size: 0.75rem;
        padding: 0.3rem 0.6rem;
        border-radius: 6px;
        margin-right: 1rem;
    }

    .action-btn {
        background-color: var(--accent-blue);
        color: white;
        border: none;
        padding: 0.5rem 1.2rem;
        border-radius: 8px;
        cursor: pointer;
        font-weight: 500;
        font-size: 0.85rem;
        transition: opacity 0.2s;
    }

    .action-btn:hover {
        opacity: 0.9;
    }

    /* Layout */
    .main-layout {
        display: flex;
        flex: 1;
    }

    .sidebar {
        width: 260px;
        background-color: var(--bg-sidebar);
        border-right: 1px solid var(--border-color);
        padding: 2rem 1.5rem;
        display: flex;
        flex-direction: column;
        gap: 2rem;
    }

    .filter-section h3 {
        font-size: 0.8rem;
        color: var(--text-sub);
        text-transform: uppercase;
        margin-bottom: 0.75rem;
        letter-spacing: 0.05em;
    }

    .filter-options {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .filter-label {
        font-size: 0.9rem;
        padding: 0.5rem;
        border-radius: 6px;
        cursor: pointer;
        transition: background 0.2s;
    }

    .filter-label:hover {
        background-color: var(--card-bg);
    }

    .filter-label.active {
        background-color: rgba(10, 132, 255, 0.15);
        color: var(--accent-blue);
        font-weight: 600;
    }

    /* Toggle Switch */
    .toggle-wrapper {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-top: 1rem;
    }

    .toggle-text {
        font-size: 0.85rem;
        color: var(--text-sub);
    }

    .switch-container {
        position: relative;
        display: inline-block;
        width: 38px;
        height: 22px;
    }

    .switch-container input {
        opacity: 0;
        width: 0;
        height: 0;
    }

    .slider {
        position: absolute;
        cursor: pointer;
        top: 0; left: 0; right: 0; bottom: 0;
        background-color: #3d3d3f;
        transition: .3s;
        border-radius: 34px;
    }

    .slider:before {
        position: absolute;
        content: "";
        height: 16px;
        width: 16px;
        left: 3px;
        bottom: 3px;
        background-color: white;
        transition: .3s;
        border-radius: 50%;
    }

    input:checked + .slider {
        background-color: var(--accent-blue);
    }

    input:checked + .slider:before {
        transform: translateX(16px);
    }

    /* Grid Area */
    .content-grid-wrapper {
        flex: 1;
        padding: 2rem;
        overflow-y: auto;
        max-height: calc(100vh - 70px);
    }

    .cards-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: 1.5rem;
    }

    /* Card Item (Glassmorphism) */
    .card-item {
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.25rem;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 200px;
        backdrop-filter: blur(12px);
        transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
        cursor: pointer;
    }

    .card-item:hover {
        transform: translateY(-4px);
        border-color: rgba(255, 255, 255, 0.2);
        background: var(--card-hover);
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    }

    .card-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.5rem;
    }

    .platform-badge {
        font-size: 0.7rem;
        font-weight: 700;
        padding: 0.2rem 0.4rem;
        border-radius: 4px;
        text-transform: uppercase;
    }

    .platform-badge.weibo {
        background-color: rgba(255, 69, 58, 0.15);
        color: var(--accent-red);
    }

    .platform-badge.zhihu {
        background-color: rgba(10, 132, 255, 0.15);
        color: var(--accent-blue);
    }

    .score-badge {
        font-size: 0.85rem;
        font-weight: 700;
        color: var(--accent-green);
    }

    .card-title {
        font-size: 0.95rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        line-height: 1.4;
    }

    .card-desc {
        font-size: 0.8rem;
        color: var(--text-sub);
        line-height: 1.4;
        margin-bottom: 1rem;
        flex: 1;
    }

    .card-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-top: 1px solid var(--border-color);
        padding-top: 0.75rem;
        font-size: 0.7rem;
        color: var(--text-sub);
    }

    /* Analyze Button */
    .analyze-btn {
        background-color: transparent;
        color: var(--accent-blue);
        border: 1px solid var(--accent-blue);
        border-radius: 6px;
        padding: 0.35rem 0.75rem;
        cursor: pointer;
        font-size: 0.75rem;
        font-weight: 600;
        transition: background 0.2s;
    }

    .analyze-btn:hover {
        background-color: rgba(10, 132, 255, 0.1);
    }

    .analyze-btn.loading {
        opacity: 0.5;
        cursor: not-allowed;
    }

    /* Modal Styling */
    .modal-overlay {
        position: fixed;
        inset: 0;
        background-color: rgba(0, 0, 0, 0.75);
        backdrop-filter: blur(8px);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 1000;
        transition: opacity 0.3s ease;
    }

    .modal-card {
        background-color: var(--bg-sidebar);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        width: 90%;
        max-width: 600px;
        padding: 2rem;
        box-shadow: 0 12px 40px rgba(0,0,0,0.6);
        position: relative;
    }

    .modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }

    .close-btn {
        background: transparent;
        border: none;
        color: var(--text-sub);
        font-size: 1.5rem;
        cursor: pointer;
    }

    .close-btn:hover {
        color: var(--text-main);
    }

    .source-link {
        color: var(--accent-blue);
        text-decoration: none;
        font-size: 0.8rem;
        margin-top: 0.5rem;
        display: inline-block;
    }

    .modal-divider {
        border: 0;
        height: 1px;
        background: var(--border-color);
        margin: 1.5rem 0;
    }

    .analysis-box {
        display: flex;
        flex-direction: column;
        gap: 1.25rem;
    }

    .analysis-item .label {
        font-size: 0.7rem;
        text-transform: uppercase;
        color: var(--text-sub);
        letter-spacing: 0.05em;
        display: block;
        margin-bottom: 0.35rem;
    }

    .analysis-item p {
        font-size: 0.9rem;
        line-height: 1.5;
    }

    .analysis-footer {
        display: flex;
        justify-content: space-between;
        margin-top: 2rem;
        background-color: rgba(255, 255, 255, 0.02);
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid var(--border-color);
    }

    .footer-stat .val {
        display: block;
        font-size: 1.1rem;
        font-weight: 700;
        margin-top: 0.25rem;
    }

    .score-high { color: var(--accent-green); }
    .score-med { color: var(--accent-orange); }

    .hide {
        display: none !important;
    }
    ```

- [ ] **Step 3: 编写交互核心逻辑 static/app.js**
    ```javascript
    let allEvents = [];

    // 初始化加载
    document.addEventListener("DOMContentLoaded", () => {
        loadEvents();
        
        document.getElementById("refresh-btn").addEventListener("click", triggerCrawl);
        document.getElementById("close-modal-btn").addEventListener("click", closeModal);
        document.getElementById("show-low-value-toggle").addEventListener("change", renderGrid);
        
        // 绑定左侧筛选项点击
        document.querySelectorAll(".sidebar [data-platform]").forEach(el => {
            el.addEventListener("click", (e) => {
                document.querySelectorAll("[data-platform]").forEach(lbl => lbl.classList.remove("active"));
                e.target.classList.add("active");
                renderGrid();
            });
        });
        
        document.querySelectorAll(".sidebar [data-difficulty]").forEach(el => {
            el.addEventListener("click", (e) => {
                document.querySelectorAll("[data-difficulty]").forEach(lbl => lbl.classList.remove("active"));
                e.target.classList.add("active");
                renderGrid();
            });
        });
    });

    async function loadEvents() {
        const grid = document.getElementById("cards-grid");
        grid.innerHTML = '<div style="color: var(--text-sub); grid-column: 1/-1; text-align: center; padding: 3rem;">正在获取热点数据...</div>';
        
        try {
            const res = await fetch("/api/events");
            allEvents = await res.json();
            
            // 判断是否启用了降级源
            const hasFallback = allEvents.some(e => e.popularity <= 100000 && e.popularity > 50000);
            const warningBadge = document.getElementById("warning-badge");
            if (hasFallback) {
                warningBadge.classList.remove("hide");
            } else {
                warningBadge.classList.add("hide");
            }
            
            renderGrid();
        } catch (e) {
            grid.innerHTML = '<div style="color: var(--accent-red); grid-column: 1/-1; text-align: center; padding: 3rem;">拉取数据失败，请检查后端运行状态。</div>';
        }
    }

    async function triggerCrawl() {
        const btn = document.getElementById("refresh-btn");
        btn.disabled = true;
        btn.textContent = "爬取并清理中...";
        
        try {
            await fetch("/api/trigger-crawl", { method: "POST" });
            await loadEvents();
        } catch (e) {
            alert("刷新抓取失败，请检查网络或后端服务。");
        } finally {
            btn.disabled = false;
            btn.textContent = "🔄 刷新抓取热点";
        }
    }

    function renderGrid() {
        const grid = document.getElementById("cards-grid");
        grid.innerHTML = "";
        
        // 读取当前筛选配置
        const selectedPlatform = document.querySelector("[data-platform].active").dataset.platform;
        const selectedDifficulty = document.querySelector("[data-difficulty].active").dataset.difficulty;
        const showLowValue = document.getElementById("show-low-value-toggle").checked;
        
        const filtered = allEvents.filter(e => {
            // 1. 平台过滤
            if (selectedPlatform !== "all" && e.platform !== selectedPlatform) return false;
            // 2. 状态/价值过滤
            if (e.status === "low_value" && !showLowValue) return false;
            // 3. 难度过滤
            if (selectedDifficulty !== "all" && e.difficulty !== selectedDifficulty) return false;
            return true;
        });
        
        if (filtered.length === 0) {
            grid.innerHTML = '<div style="color: var(--text-sub); grid-column: 1/-1; text-align: center; padding: 3rem;">暂无匹配的数据。</div>';
            return;
        }
        
        filtered.forEach(e => {
            const card = document.createElement("div");
            card.className = "card-item";
            
            let statusText = "待分析";
            let scoreText = "";
            let btnHtml = `<button class="analyze-btn" onclick="startAnalysis(event, ${e.id}, '${e.title}', '${e.platform}')">🧠 AI 分析</button>`;
            
            if (e.status === "analyzed") {
                statusText = "已分析";
                scoreText = `⭐ ${e.value_score} 分`;
                btnHtml = "";
            } else if (e.status === "low_value") {
                statusText = "低价值";
                scoreText = `💤 ${e.value_score} 分`;
                btnHtml = "";
            } else if (e.status === "failed") {
                statusText = "失败";
                btnHtml = `<button class="analyze-btn" onclick="startAnalysis(event, ${e.id}, '${e.title}', '${e.platform}')">🔄 重试</button>`;
            }
            
            card.innerHTML = `
                <div>
                    <div class="card-top">
                        <span class="platform-badge ${e.platform}">${e.platform === "weibo" ? "微博" : "知乎"}</span>
                        <span class="score-badge">${scoreText}</span>
                    </div>
                    <div class="card-title">${e.title}</div>
                    <div class="card-desc">${e.analysis_summary || "暂无 AI 分析报告，请点击下方进行深度需求挖掘。"}</div>
                </div>
                <div class="card-meta">
                    <span>🔥 指数: ${e.popularity.toLocaleString()}</span>
                    ${btnHtml}
                </div>
            `;
            
            // 点击卡片进入详情
            card.addEventListener("click", () => {
                if (e.status === "analyzed" || e.status === "low_value") {
                    showDetails(e);
                }
            });
            
            grid.appendChild(card);
        });
    }

    async function startAnalysis(event, eventId, title, platform) {
        event.stopPropagation(); // 阻止卡片点击事件触发弹窗
        const btn = event.target;
        btn.disabled = true;
        btn.textContent = "分析中...";
        btn.classList.add("loading");
        
        try {
            const res = await fetch(`/api/events/${eventId}/analyze`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title, platform })
            });
            const data = await res.json();
            if (data.status === "success") {
                // 重新拉取
                await loadEvents();
            } else {
                alert("AI 分析出错，请重试。");
            }
        } catch (e) {
            alert("请求异常，请检查后端 API。");
        } finally {
            btn.disabled = false;
            btn.textContent = "🧠 AI 分析";
            btn.classList.remove("loading");
        }
    }

    function showDetails(e) {
        document.getElementById("modal-title").textContent = e.title;
        document.getElementById("modal-platform").textContent = e.platform === "weibo" ? "微博热搜" : "知乎热榜";
        document.getElementById("modal-platform").className = `modal-platform platform-badge ${e.platform}`;
        document.getElementById("modal-url").href = e.url;
        
        document.getElementById("modal-audience").textContent = e.target_audience || "无";
        document.getElementById("modal-pain").textContent = e.pain_point || "无";
        document.getElementById("modal-concept").textContent = e.product_concept || "无";
        
        const difficultyText = {
            "easy": "简单 (插件/脚本)",
            "medium": "中等 (小程序/网站)",
            "hard": "困难 (深研/AI/大数据)"
        }[e.difficulty] || e.difficulty;
        
        document.getElementById("modal-difficulty").textContent = difficultyText;
        
        const scoreEl = document.getElementById("modal-score");
        scoreEl.textContent = `${e.value_score} 分`;
        if (e.value_score >= 8) {
            scoreEl.className = "val score-high";
        } else {
            scoreEl.className = "val score-med";
        }
        
        document.getElementById("detail-modal").classList.remove("hide");
    }

    function closeModal() {
        document.getElementById("detail-modal").classList.add("hide");
    }
    ```

---

## 验证方案

### 自动化验证
*   运行后端所有的测试套件：
    ```bash
    pytest tests/ -v
    ```
    期望输出：`tests/test_database.py`、`tests/test_crawler.py` 以及 `tests/test_ai_analyst.py` 均执行并显示绿色的 `PASS`。

### 手动功能联调验证
1.  **启动后端服务**：在终端启动 uvicorn：
    ```bash
    uvicorn main:app --host 127.0.0.1 --port 8000 --reload
    ```
2.  **打开浏览器**：访问 `http://127.0.0.1:8000/`，应能渲染出带暗黑科技风样式的“舆情热点需求捕手”看板。
3.  **触发爬网**：点击右上角“🔄 刷新抓取热点”按钮，等待 2-3 秒，验证是否显示出微博和知乎热榜的原始卡片列表。
4.  **AI 分析校验**：
    *   在 `.env` 中填入合规的 `GEMINI_API_KEY`。
    *   在网页中找一个打工、职场或民生相关的热点事件，点击“🧠 AI 分析”。
    *   等待其分析完成后，确认卡片上生成了价值评分和 AI 简短摘要，且卡片颜色/标记已更新。
    *   点击此卡片，核实模态框弹窗正确弹出，其内部“目标客群”、“痛点”、“产品构想”等维度数据展示完整。
