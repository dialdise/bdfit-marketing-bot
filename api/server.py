"""
FastAPI backend — BDFit Marketing Bot Dashboard
Manages agents, database, scheduling, and WebSocket for live updates.
"""

import json
import os
import sys
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.news_agent import run_news_agent
from agents.content_agent import generate_content

# Load .env only if it exists (local dev). Cloud platforms inject vars directly.
_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    load_dotenv(_env)

BASE_DIR = Path(__file__).parent.parent
# On Railway, /data may not be writable; use /tmp as fallback
_data_dir = BASE_DIR / "data"
_data_dir.mkdir(exist_ok=True)
DB_PATH = _data_dir / "bdfit.db"
DASHBOARD_DIR = BASE_DIR / "dashboard"

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
NEWS_HOUR = int(os.getenv("NEWS_SCHEDULE_HOUR", 9))
NEWS_MINUTE = int(os.getenv("NEWS_SCHEDULE_MINUTE", 0))

# Global state
connected_clients: list[WebSocket] = []
agent_status = {
    "news_agent": {
        "name": "News Scout",
        "status": "idle",
        "last_run": None,
        "next_run": None,
        "runs_today": 0,
        "icon": "📰",
    },
    "content_agent": {
        "name": "Content Creator",
        "status": "idle",
        "last_run": None,
        "pending_queue": 0,
        "completed_today": 0,
        "icon": "✍️",
    },
}


async def broadcast(event: str, data: dict):
    """Push update to all connected WebSocket clients."""
    message = json.dumps({"event": event, "data": data, "ts": datetime.now().isoformat()})
    dead = []
    for ws in connected_clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_clients.remove(ws)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS news_runs (
                id TEXT PRIMARY KEY,
                run_at TEXT,
                articles_fetched INTEGER,
                articles_filtered INTEGER,
                ideas_generated INTEGER
            );

            CREATE TABLE IF NOT EXISTS news_articles (
                id TEXT PRIMARY KEY,
                run_id TEXT,
                title TEXT,
                source TEXT,
                link TEXT,
                published TEXT,
                relevance_score INTEGER,
                why_it_matters TEXT
            );

            CREATE TABLE IF NOT EXISTS content_ideas (
                id TEXT PRIMARY KEY,
                run_id TEXT,
                platform TEXT,
                format TEXT,
                title TEXT,
                hook TEXT,
                description TEXT,
                trend_connection TEXT,
                news_connection TEXT,
                estimated_reach TEXT,
                hashtags TEXT,
                status TEXT DEFAULT 'pending',
                rejection_reason TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS generated_content (
                id TEXT PRIMARY KEY,
                idea_id TEXT,
                platform TEXT,
                format TEXT,
                content_json TEXT,
                created_at TEXT,
                status TEXT DEFAULT 'draft'
            );
        """)
        await db.commit()


async def save_news_run(result: dict):
    run_id = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO news_runs VALUES (?, ?, ?, ?, ?)",
            (
                run_id,
                result["run_timestamp"],
                result["stats"]["articles_fetched"],
                result["stats"]["articles_filtered"],
                result["stats"]["ideas_generated"],
            ),
        )

        for article in result.get("filtered_news", []):
            await db.execute(
                "INSERT OR IGNORE INTO news_articles VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()), run_id,
                    article.get("title"), article.get("source"),
                    article.get("link"), article.get("published"),
                    article.get("relevance_score", 5),
                    article.get("why_it_matters", ""),
                ),
            )

        for idea in result.get("content_ideas", []):
            await db.execute(
                "INSERT OR IGNORE INTO content_ideas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    idea.get("id", str(uuid.uuid4())), run_id,
                    idea.get("platform"), idea.get("format"),
                    idea.get("title"), idea.get("hook"),
                    idea.get("description"), idea.get("trend_connection"),
                    idea.get("news_connection"), idea.get("estimated_reach"),
                    json.dumps(idea.get("hashtags", [])),
                    "pending", None,
                    datetime.now().isoformat(),
                ),
            )

        await db.commit()
    return run_id


async def scheduled_news_job():
    """Called by APScheduler at 9 AM daily."""
    agent_status["news_agent"]["status"] = "running"
    await broadcast("agent_update", agent_status)

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, lambda: run_news_agent(API_KEY))
        await save_news_run(result)
        agent_status["news_agent"]["status"] = "idle"
        agent_status["news_agent"]["last_run"] = datetime.now().isoformat()
        agent_status["news_agent"]["runs_today"] += 1
        await broadcast("news_complete", result)
    except Exception as e:
        agent_status["news_agent"]["status"] = "error"
        await broadcast("agent_error", {"agent": "news_agent", "error": str(e)})
    finally:
        await broadcast("agent_update", agent_status)


scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler.add_job(
        scheduled_news_job, "cron",
        hour=NEWS_HOUR, minute=NEWS_MINUTE,
        id="news_agent_job", replace_existing=True
    )
    scheduler.start()
    next_run = scheduler.get_job("news_agent_job").next_run_time
    agent_status["news_agent"]["next_run"] = next_run.isoformat() if next_run else None
    print(f"[Server] Scheduler started. News agent runs at {NEWS_HOUR:02d}:{NEWS_MINUTE:02d}")
    yield
    scheduler.shutdown()


app = FastAPI(title="BDFit Marketing Bot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── REST Endpoints ────────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    return {"agents": agent_status, "timestamp": datetime.now().isoformat()}


@app.get("/api/news")
async def get_news(limit: int = 20):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM news_articles ORDER BY rowid DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
    return {"articles": [dict(r) for r in rows]}


@app.get("/api/ideas")
async def get_ideas(status: str = None, platform: str = None):
    query = "SELECT * FROM content_ideas"
    params = []
    conditions = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if platform:
        conditions.append("platform = ?")
        params.append(platform)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY rowid DESC"

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

    ideas = []
    for r in rows:
        idea = dict(r)
        try:
            idea["hashtags"] = json.loads(idea.get("hashtags", "[]"))
        except Exception:
            idea["hashtags"] = []
        ideas.append(idea)
    return {"ideas": ideas}


class IdeaAction(BaseModel):
    action: str  # "approve" | "reject"
    rejection_reason: str = None


@app.post("/api/ideas/{idea_id}/review")
async def review_idea(idea_id: str, body: IdeaAction, background_tasks: BackgroundTasks):
    if body.action not in ("approve", "reject"):
        raise HTTPException(400, "action must be 'approve' or 'reject'")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE content_ideas SET status = ?, rejection_reason = ? WHERE id = ?",
            (body.action + "d", body.rejection_reason, idea_id),
        )
        await db.commit()

        if body.action == "approve":
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM content_ideas WHERE id = ?", (idea_id,)) as cur:
                row = await cur.fetchone()
            if row:
                idea = dict(row)
                try:
                    idea["hashtags"] = json.loads(idea.get("hashtags", "[]"))
                except Exception:
                    idea["hashtags"] = []
                background_tasks.add_task(_run_content_agent, idea)

    await broadcast("idea_reviewed", {"idea_id": idea_id, "action": body.action})
    return {"ok": True, "idea_id": idea_id, "status": body.action + "d"}


async def _run_content_agent(idea: dict):
    agent_status["content_agent"]["status"] = "running"
    await broadcast("agent_update", agent_status)

    loop = asyncio.get_event_loop()
    try:
        content = await loop.run_in_executor(None, lambda: generate_content(idea, API_KEY))
        content_id = str(uuid.uuid4())
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO generated_content VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    content_id, idea["id"],
                    idea.get("platform"), idea.get("format"),
                    json.dumps(content),
                    datetime.now().isoformat(),
                    "draft",
                ),
            )
            await db.commit()

        agent_status["content_agent"]["status"] = "idle"
        agent_status["content_agent"]["last_run"] = datetime.now().isoformat()
        agent_status["content_agent"]["completed_today"] += 1
        await broadcast("content_ready", {"idea_id": idea["id"], "content_id": content_id, "content": content})
    except Exception as e:
        agent_status["content_agent"]["status"] = "error"
        await broadcast("agent_error", {"agent": "content_agent", "error": str(e)})
    finally:
        await broadcast("agent_update", agent_status)


@app.get("/api/content")
async def get_generated_content(idea_id: str = None):
    query = "SELECT gc.*, ci.title as idea_title, ci.platform as idea_platform FROM generated_content gc LEFT JOIN content_ideas ci ON gc.idea_id = ci.id"
    params = []
    if idea_id:
        query += " WHERE gc.idea_id = ?"
        params.append(idea_id)
    query += " ORDER BY gc.rowid DESC"

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

    results = []
    for r in rows:
        item = dict(r)
        try:
            item["content"] = json.loads(item.get("content_json", "{}"))
        except Exception:
            item["content"] = {}
        results.append(item)
    return {"content": results}


@app.post("/api/agents/news/trigger")
async def trigger_news_agent(background_tasks: BackgroundTasks):
    """Manually trigger the news agent."""
    if agent_status["news_agent"]["status"] == "running":
        raise HTTPException(409, "News agent is already running")
    background_tasks.add_task(scheduled_news_job)
    return {"ok": True, "message": "News agent triggered"}


# ─── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    await websocket.send_text(json.dumps({
        "event": "connected",
        "data": {"agents": agent_status},
        "ts": datetime.now().isoformat(),
    }))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)


# ─── Serve Dashboard ───────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")


@app.get("/")
async def serve_dashboard():
    return FileResponse(str(DASHBOARD_DIR / "index.html"))
