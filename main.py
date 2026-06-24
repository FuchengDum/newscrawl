import os
import threading
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import markdown as md_lib
import database
import crawler
import ai_analyst

class AnalyzePayload(BaseModel):
    title: str
    platform: str

class BatchAnalyzePayload(BaseModel):
    date: str
    platform: Optional[str] = None

# 批量分析全局状态
batch_state = {
    "running": False,
    "total": 0,
    "completed": 0,
    "failed": 0,
    "failed_titles": [],
    "lock": threading.Lock(),
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库，并进行自动数据清理
    database.init_db()
    database.delete_old_unanalyzed_events()
    yield

app = FastAPI(title="Hot News Needs Miner", lifespan=lifespan)

@app.get("/api/events")
def get_events(
    date: Optional[str] = None,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    difficulty: Optional[str] = None,
    show_low_value: bool = True
):
    # 获取筛选后的事件列表
    try:
        # 将 "all" 转换为 None（前端传 "all" 表示不筛选）
        if platform == "all":
            platform = None
        if status == "all":
            status = None
        if difficulty == "all":
            difficulty = None
        return database.get_events_filtered(
            date=date,
            platform=platform,
            status=status,
            difficulty=difficulty,
            show_low_value=show_low_value
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dates")
def get_dates():
    """返回所有可用日期列表（降序）"""
    try:
        dates = database.get_available_dates()
        return {"dates": dates}
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
def analyze_event(event_id: int, payload: AnalyzePayload):
    if not database.event_exists(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    try:
        analysis = ai_analyst.trigger_event_analysis(event_id, payload.title, payload.platform)
        return {"status": "success", "analysis": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------- 批量分析 ----------

def _run_batch_analysis(pending_items):
    """在后台线程中执行批量分析，使用 5 路并发"""
    def analyze_one(item):
        event_id, title, platform = item
        try:
            ai_analyst.trigger_event_analysis(event_id, title, platform)
            with batch_state["lock"]:
                batch_state["completed"] += 1
        except Exception:
            with batch_state["lock"]:
                batch_state["failed"] += 1
                batch_state["failed_titles"].append(title)

    try:
        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(analyze_one, pending_items)
    finally:
        with batch_state["lock"]:
            batch_state["running"] = False


@app.post("/api/batch-analyze")
def batch_analyze(payload: BatchAnalyzePayload):
    """启动批量分析任务"""
    with batch_state["lock"]:
        if batch_state["running"]:
            raise HTTPException(status_code=409, detail="已有批量分析任务正在运行")

    # 查询待分析事件
    platform = payload.platform if payload.platform and payload.platform != "all" else None
    pending = database.get_batch_pending(payload.date, platform)

    if not pending:
        return {"status": "empty", "total": 0, "message": "没有待分析的事件"}

    # 设置全局状态
    with batch_state["lock"]:
        batch_state["running"] = True
        batch_state["total"] = len(pending)
        batch_state["completed"] = 0
        batch_state["failed"] = 0
        batch_state["failed_titles"] = []

    # 启动后台线程
    t = threading.Thread(target=_run_batch_analysis, args=(pending,), daemon=True)
    t.start()

    return {"status": "started", "total": len(pending)}


@app.get("/api/batch-analyze/status")
def batch_analyze_status():
    """返回批量分析进度"""
    with batch_state["lock"]:
        return {
            "running": batch_state["running"],
            "total": batch_state["total"],
            "completed": batch_state["completed"],
            "failed": batch_state["failed"],
            "failed_titles": list(batch_state["failed_titles"]),
        }


# ---------- 日报生成 ----------

@app.post("/api/report/{date}")
def generate_report(date: str):
    """生成指定日期的日报"""
    try:
        events = database.get_report_data(date)
        if not events:
            raise HTTPException(status_code=404, detail=f"日期 {date} 没有符合条件的已分析高价值事件（value_score ≥ 6）")

        # 生成 Markdown
        md_str = ai_analyst.generate_daily_report_markdown(date, events)

        # 保存到 docs/reports/
        reports_dir = os.path.join(os.path.dirname(__file__), "docs", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        file_path = os.path.join(reports_dir, f"{date}-daily-report.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_str)

        # 转 HTML
        html_str = md_lib.markdown(md_str, extensions=["tables", "fenced_code"])

        return {
            "status": "success",
            "markdown": md_str,
            "html": html_str,
            "file_path": file_path
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 挂载前端静态文件目录
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
