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
