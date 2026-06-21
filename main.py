import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import database
import crawler
import ai_analyst

class AnalyzePayload(BaseModel):
    title: str
    platform: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库，并进行自动数据清理
    database.init_db()
    database.delete_old_unanalyzed_events()
    yield

app = FastAPI(title="Hot News Needs Miner", lifespan=lifespan)

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
def analyze_event(event_id: int, payload: AnalyzePayload):
    if not database.event_exists(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    try:
        analysis = ai_analyst.trigger_event_analysis(event_id, payload.title, payload.platform)
        return {"status": "success", "analysis": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 挂载前端静态文件目录
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
