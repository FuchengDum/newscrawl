import sqlite3
from datetime import datetime, timedelta, timezone

DB_FILE = "ainews.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    try:
        with conn:
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
    finally:
        conn.close()

def save_hot_event(title, url, platform, popularity):
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO hot_events (title, url, platform, popularity) VALUES (?, ?, ?, ?)",
                (title, url, platform, popularity)
            )
            event_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO need_analysis (event_id, status) VALUES (?, 'pending')",
                (event_id,)
            )
        return True
    except sqlite3.IntegrityError:
        # 标题已存在，跳过插入
        return False
    finally:
        conn.close()

def get_pending_events():
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT h.id, h.title, h.url, h.platform, h.popularity, n.status 
            FROM hot_events h
            JOIN need_analysis n ON h.id = n.event_id
            ORDER BY h.popularity DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def update_analysis(event_id, a):
    # a 是字典，包含 has_value, value_score, target_audience, pain_point, product_concept, difficulty, analysis_summary
    status = a.get("status")
    if not status:
        status = "analyzed" if a.get("has_value") and a.get("value_score", 0) >= 6 else "low_value"
    conn = get_db_connection()
    try:
        with conn:
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
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                event_id
            ))
            conn.commit()
    finally:
        conn.close()

def delete_old_unanalyzed_events():
    limit_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    try:
        with conn:
            # 删除未被分析或标记为低价值且超过 7 天的原始事件
            conn.execute("""
                DELETE FROM hot_events 
                WHERE created_at < ? AND id IN (
                    SELECT event_id FROM need_analysis WHERE status IN ('pending', 'low_value', 'failed')
                )
            """, (limit_date,))
            conn.commit()
    finally:
        conn.close()
