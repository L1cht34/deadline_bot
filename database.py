import aiosqlite
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

DB_PATH = "deadlines_bot.db"

async def init_db() -> None:
    """Инициализация таблиц базы данных."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                group_name TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT NOT NULL,
                subject TEXT NOT NULL,
                description TEXT NOT NULL,
                deadline_date DATE NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_assignments (
                user_id INTEGER NOT NULL,
                assignment_id INTEGER NOT NULL,
                is_completed INTEGER DEFAULT 0,
                completed_at TIMESTAMP,
                PRIMARY KEY (user_id, assignment_id),
                FOREIGN KEY (assignment_id) REFERENCES assignments (id) ON DELETE CASCADE
            )
        """)
        await db.commit()

async def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def register_user(telegram_id: int, group_name: str, role: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (telegram_id, group_name, role)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                group_name = excluded.group_name,
                role = excluded.role
        """, (telegram_id, group_name, role))
        await db.commit()

async def add_assignment(group_name: str, subject: str, description: str, deadline_date: str, created_by: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO assignments (group_name, subject, description, deadline_date, created_by)
            VALUES (?, ?, ?, ?, ?)
        """, (group_name, subject, description, deadline_date, created_by))
        await db.commit()
        return cursor.lastrowid

async def get_assignments_by_group(group_name: str) -> List[Dict[str, Any]]:
    """Получение всех заданий группы (для панели управления старосты)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM assignments WHERE group_name = ? ORDER BY deadline_date ASC",
            (group_name,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def delete_assignment(assignment_id: int, group_name: str) -> bool:
    """Удаление задания и всех отметок о его выполнении."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Удаляем отметки студентов по этому заданию
        await db.execute("DELETE FROM user_assignments WHERE assignment_id = ?", (assignment_id,))
        # Удаляем само задание
        cursor = await db.execute(
            "DELETE FROM assignments WHERE id = ? AND group_name = ?", 
            (assignment_id, group_name)
        )
        await db.commit()
        return cursor.rowcount > 0

async def get_user_assignments(telegram_id: int, group_name: str) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT 
                a.id, 
                a.subject, 
                a.description, 
                a.deadline_date,
                COALESCE(ua.is_completed, 0) as is_completed,
                ua.completed_at
            FROM assignments a
            LEFT JOIN user_assignments ua 
                ON a.id = ua.assignment_id AND ua.user_id = ?
            WHERE a.group_name = ?
              AND (
                  ua.is_completed IS NULL 
                  OR ua.is_completed = 0 
                  OR ua.completed_at >= datetime('now', '-2 days')
              )
            ORDER BY a.deadline_date ASC
        """
        async with db.execute(query, (telegram_id, group_name)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def toggle_assignment_status(telegram_id: int, assignment_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT is_completed FROM user_assignments WHERE user_id = ? AND assignment_id = ?",
            (telegram_id, assignment_id)
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            await db.execute("""
                INSERT INTO user_assignments (user_id, assignment_id, is_completed, completed_at)
                VALUES (?, ?, 1, CURRENT_TIMESTAMP)
            """, (telegram_id, assignment_id))
            new_status = True
        else:
            current_status = bool(row["is_completed"])
            if current_status:
                await db.execute("""
                    UPDATE user_assignments 
                    SET is_completed = 0, completed_at = NULL 
                    WHERE user_id = ? AND assignment_id = ?
                """, (telegram_id, assignment_id))
                new_status = False
            else:
                await db.execute("""
                    UPDATE user_assignments 
                    SET is_completed = 1, completed_at = CURRENT_TIMESTAMP 
                    WHERE user_id = ? AND assignment_id = ?
                """, (telegram_id, assignment_id))
                new_status = True

        await db.commit()
        return new_status

async def get_all_students() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT telegram_id, group_name, role FROM users") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_upcoming_and_overdue_for_user(telegram_id: int, group_name: str) -> Dict[str, List[Dict[str, Any]]]:
    today = date.today()
    assignments = await get_user_assignments(telegram_id, group_name)

    upcoming = []
    overdue = []

    for item in assignments:
        if item["is_completed"]:
            continue

        item_deadline = datetime.strptime(item["deadline_date"], "%Y-%m-%d").date()
        days_left = (item_deadline - today).days

        if days_left < 0:
            overdue.append({**item, "days_overdue": abs(days_left)})
        elif days_left in (7, 3, 2, 1):
            upcoming.append({**item, "days_left": days_left})

    return {"upcoming": upcoming, "overdue": overdue}