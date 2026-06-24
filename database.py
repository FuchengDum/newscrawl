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
    conn = get_db_connection()
    try:
        query = """
            SELECT h.id, h.title, h.url, h.platform, h.popularity,
                   n.status, n.value_score, n.target_audience, n.pain_point,
                   n.product_concept, n.difficulty, n.analysis_summary, n.analyzed_at
            FROM hot_events h
            JOIN need_analysis n ON h.id = n.event_id
            WHERE 1=1
        """
        params = []

        if date:
            query += " AND date(datetime(h.created_at, '+8 hours')) = ?"
            params.append(date)

        if platform:
            query += " AND h.platform = ?"
            params.append(platform)

        if status:
            query += " AND n.status = ?"
            params.append(status)
        elif not show_low_value:
            # 当 status=None 时，根据 show_low_value 决定是否排除 low_value
            query += " AND n.status != 'low_value'"

        if difficulty:
            query += " AND n.difficulty = ?"
            params.append(difficulty)

        query += " ORDER BY h.popularity DESC"

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# 保留原函数名作为兼容别名
def get_pending_events():
    return get_events_filtered()


def get_available_dates():
    """
    返回所有不重复日期列表（降序），使用 UTC+8 转换。
    返回: ['2026-06-23', '2026-06-21']
    """
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT DISTINCT date(datetime(created_at, '+8 hours')) as local_date
            FROM hot_events
            ORDER BY local_date DESC
        """).fetchall()
        return [r["local_date"] for r in rows]
    finally:
        conn.close()


def get_report_data(date):
    """
    查询指定日期（UTC+8）status='analyzed' 且 value_score >= 6 的事件。
    按 value_score DESC 排序。返回完整字段用于日报生成。
    """
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT h.id, h.title, h.url, h.platform, h.popularity,
                   n.status, n.value_score, n.target_audience, n.pain_point,
                   n.product_concept, n.difficulty, n.analysis_summary, n.analyzed_at
            FROM hot_events h
            JOIN need_analysis n ON h.id = n.event_id
            WHERE date(datetime(h.created_at, '+8 hours')) = ?
              AND n.status = 'analyzed'
              AND n.value_score >= 6
            ORDER BY n.value_score DESC
        """, (date,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_batch_pending(date, platform=None):
    """
    查询指定日期（UTC+8）+ 平台下所有 status='pending' 或 'failed' 的事件。
    返回 [(id, title, platform), ...]
    """
    conn = get_db_connection()
    try:
        query = """
            SELECT h.id, h.title, h.platform
            FROM hot_events h
            JOIN need_analysis n ON h.id = n.event_id
            WHERE date(datetime(h.created_at, '+8 hours')) = ?
              AND n.status IN ('pending', 'failed')
        """
        params = [date]

        if platform:
            query += " AND h.platform = ?"
            params.append(platform)

        rows = conn.execute(query, params).fetchall()
        return [(r["id"], r["title"], r["platform"]) for r in rows]
    finally:
        conn.close()

def reset_event_status_to_pending(event_ids: list[int]):
    """将指定事件的分析状态重置为 pending"""
    if not event_ids:
        return
    conn = get_db_connection()
    try:
        with conn:
            placeholder = ",".join("?" for _ in event_ids)
            conn.execute(
                f"UPDATE need_analysis SET status = 'pending' WHERE event_id IN ({placeholder})",
                event_ids
            )
            conn.commit()
    finally:
        conn.close()


def event_exists(event_id: int) -> bool:
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT 1 FROM hot_events WHERE id = ?", (event_id,))
        return cursor.fetchone() is not None
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
