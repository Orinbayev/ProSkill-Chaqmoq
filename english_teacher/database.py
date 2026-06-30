"""
SQLite database for English Teacher bot.
ChaqmoqApp's main PostgreSQL is separate — this bot uses its own lightweight DB.
"""
import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

# Stored next to this file; persists across restarts but NOT across Render re-deploys.
# For production persistence, migrate to PostgreSQL later.
DB_PATH = Path(__file__).parent / "english_bot.db"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            first_name    TEXT,
            level         TEXT    DEFAULT 'A1',
            streak        INTEGER DEFAULT 0,
            last_day      TEXT,
            created_at    TEXT    DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS words (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER,
            word          TEXT,
            translation   TEXT,
            definition    TEXT,
            example       TEXT,
            memory_tip    TEXT,
            date_added    TEXT,
            times_tested  INTEGER DEFAULT 0,
            times_correct INTEGER DEFAULT 0,
            UNIQUE(user_id, word),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS daily_lessons (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            lesson_date TEXT,
            words_json  TEXT,
            test_score  INTEGER,
            completed   INTEGER DEFAULT 0,
            UNIQUE(user_id, lesson_date),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)
    c.commit()
    c.close()


# ── users ─────────────────────────────────────────────────────────────────────

def create_user(user_id: int, username: str, first_name: str):
    c = _conn()
    c.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?,?,?)",
        (user_id, username or "", first_name or ""),
    )
    c.commit()
    c.close()


def get_user(user_id: int) -> dict | None:
    c = _conn()
    row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    c.close()
    return dict(row) if row else None


def get_all_users() -> list:
    c = _conn()
    rows = c.execute("SELECT * FROM users").fetchall()
    c.close()
    return [dict(r) for r in rows]


def update_streak(user_id: int):
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    c = _conn()
    row = c.execute("SELECT last_day, streak FROM users WHERE user_id=?", (user_id,)).fetchone()
    if row:
        last, streak = row["last_day"], row["streak"]
        new_streak = (streak + 1) if last == yesterday else (1 if last != today else streak)
        c.execute(
            "UPDATE users SET streak=?, last_day=? WHERE user_id=?",
            (new_streak, today, user_id),
        )
    c.commit()
    c.close()


def update_level(user_id: int, level: str):
    c = _conn()
    c.execute("UPDATE users SET level=? WHERE user_id=?", (level, user_id))
    c.commit()
    c.close()


# ── lessons ───────────────────────────────────────────────────────────────────

def get_today_lesson(user_id: int) -> dict | None:
    today = date.today().isoformat()
    c = _conn()
    row = c.execute(
        "SELECT * FROM daily_lessons WHERE user_id=? AND lesson_date=?", (user_id, today)
    ).fetchone()
    c.close()
    return dict(row) if row else None


def save_lesson(user_id: int, words: list):
    today = date.today().isoformat()
    c = _conn()
    c.execute(
        "INSERT OR IGNORE INTO daily_lessons (user_id, lesson_date, words_json) VALUES (?,?,?)",
        (user_id, today, json.dumps(words, ensure_ascii=False)),
    )
    for w in words:
        c.execute(
            "INSERT OR IGNORE INTO words"
            " (user_id, word, translation, definition, example, memory_tip, date_added)"
            " VALUES (?,?,?,?,?,?,?)",
            (user_id, w["word"].lower(), w["translation"], w["definition"],
             w["example"], w.get("memory_tip", ""), today),
        )
    c.commit()
    c.close()


def save_test_result(user_id: int, score: int, wrong_words: list):
    today = date.today().isoformat()
    c = _conn()
    c.execute(
        "UPDATE daily_lessons SET test_score=?, completed=1"
        " WHERE user_id=? AND lesson_date=?",
        (score, user_id, today),
    )
    c.commit()
    c.close()


def record_word_result(user_id: int, word: str, correct: bool):
    c = _conn()
    if correct:
        c.execute(
            "UPDATE words SET times_tested=times_tested+1, times_correct=times_correct+1"
            " WHERE user_id=? AND word=?",
            (user_id, word.lower()),
        )
    else:
        c.execute(
            "UPDATE words SET times_tested=times_tested+1 WHERE user_id=? AND word=?",
            (user_id, word.lower()),
        )
    c.commit()
    c.close()


# ── word queries ──────────────────────────────────────────────────────────────

def get_learned_words(user_id: int, limit: int = 60) -> list:
    c = _conn()
    rows = c.execute(
        "SELECT word FROM words WHERE user_id=? ORDER BY date_added DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    c.close()
    return [r["word"] for r in rows]


def get_words_for_review(user_id: int, limit: int = 5) -> list:
    c = _conn()
    rows = c.execute(
        """SELECT word, translation, definition, example, memory_tip
           FROM words
           WHERE user_id=? AND times_tested > 0
           ORDER BY (times_correct * 1.0 / times_tested) ASC, times_tested DESC
           LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_words_by_list(user_id: int, word_list: list) -> list:
    if not word_list:
        return []
    c = _conn()
    ph = ",".join("?" * len(word_list))
    rows = c.execute(
        f"SELECT word, translation, definition, example, memory_tip FROM words"
        f" WHERE user_id=? AND word IN ({ph})",
        (user_id, *[w.lower() for w in word_list]),
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_stats(user_id: int) -> dict:
    c = _conn()
    total = c.execute("SELECT COUNT(*) FROM words WHERE user_id=?", (user_id,)).fetchone()[0]
    done = c.execute(
        "SELECT COUNT(*) FROM daily_lessons WHERE user_id=? AND completed=1", (user_id,)
    ).fetchone()[0]
    avg = c.execute(
        "SELECT AVG(test_score*20.0) FROM daily_lessons"
        " WHERE user_id=? AND test_score IS NOT NULL",
        (user_id,),
    ).fetchone()[0]
    streak = c.execute("SELECT streak FROM users WHERE user_id=?", (user_id,)).fetchone()
    c.close()
    return {
        "total_words": total,
        "done_lessons": done,
        "avg_score": round(avg or 0, 1),
        "streak": streak["streak"] if streak else 0,
    }
