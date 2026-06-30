"""
SQLite database for English Teacher bot.
Har bir dars sana bo'yicha saqlanadi — foydalanuvchi istalgan sanaga o'tishi mumkin.
"""
import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "english_bot.db"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = _conn()
    # Migrate existing DB: add new columns if absent
    try:
        c = _conn()
        for col, defval in [
            ("topic_uz", "''"), ("topic_en", "''"), ("test_total", "5"),
        ]:
            try:
                c.execute(f"ALTER TABLE daily_lessons ADD COLUMN {col} TEXT DEFAULT {defval}")
                c.commit()
            except Exception:
                pass
        c.close()
    except Exception:
        pass

    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            first_name    TEXT,
            level         TEXT    DEFAULT 'A1',
            streak        INTEGER DEFAULT 0,
            last_day      TEXT,
            start_date    TEXT,
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
            topic_uz    TEXT    DEFAULT '',
            topic_en    TEXT    DEFAULT '',
            test_score  INTEGER,
            test_total  INTEGER DEFAULT 5,
            completed   INTEGER DEFAULT 0,
            UNIQUE(user_id, lesson_date),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)
    c.commit()
    c.close()


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(user_id: int, username: str, first_name: str):
    today = date.today().isoformat()
    c = _conn()
    c.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name, start_date) VALUES (?,?,?,?)",
        (user_id, username or "", first_name or "", today),
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
        c.execute("UPDATE users SET streak=?, last_day=? WHERE user_id=?", (new_streak, today, user_id))
    c.commit()
    c.close()


def update_level(user_id: int, level: str):
    c = _conn()
    c.execute("UPDATE users SET level=? WHERE user_id=?", (level, user_id))
    c.commit()
    c.close()


# ── Lessons (date-based) ──────────────────────────────────────────────────────

def get_lesson_for_date(user_id: int, lesson_date: str) -> dict | None:
    c = _conn()
    row = c.execute(
        "SELECT * FROM daily_lessons WHERE user_id=? AND lesson_date=?",
        (user_id, lesson_date),
    ).fetchone()
    c.close()
    return dict(row) if row else None


def get_today_lesson(user_id: int) -> dict | None:
    return get_lesson_for_date(user_id, date.today().isoformat())


def save_lesson_for_date(user_id: int, words: list, lesson_date: str,
                         topic_uz: str = "", topic_en: str = ""):
    c = _conn()
    c.execute(
        "INSERT OR IGNORE INTO daily_lessons"
        " (user_id, lesson_date, words_json, topic_uz, topic_en) VALUES (?,?,?,?,?)",
        (user_id, lesson_date, json.dumps(words, ensure_ascii=False), topic_uz, topic_en),
    )
    for w in words:
        c.execute(
            "INSERT OR IGNORE INTO words"
            " (user_id, word, translation, definition, example, memory_tip, date_added)"
            " VALUES (?,?,?,?,?,?,?)",
            (user_id, w["word"].lower(), w["translation"], w["definition"],
             w["example"], w.get("memory_tip", ""), lesson_date),
        )
    c.commit()
    c.close()


def save_lesson(user_id: int, words: list, topic_uz: str = "", topic_en: str = ""):
    save_lesson_for_date(user_id, words, date.today().isoformat(), topic_uz, topic_en)


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


def save_test_result_for_date(user_id: int, score: int, wrong_words: list,
                              lesson_date: str, total: int = 5):
    c = _conn()
    c.execute(
        "UPDATE daily_lessons SET test_score=?, test_total=?, completed=1"
        " WHERE user_id=? AND lesson_date=?",
        (score, total, user_id, lesson_date),
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


# ── Date navigation ───────────────────────────────────────────────────────────

def get_last_lesson_date(user_id: int) -> str:
    """Returns the latest lesson date, or today if none."""
    c = _conn()
    row = c.execute(
        "SELECT MAX(lesson_date) as d FROM daily_lessons WHERE user_id=?", (user_id,)
    ).fetchone()
    c.close()
    return row["d"] if row and row["d"] else date.today().isoformat()


def get_next_lesson_date(user_id: int) -> str:
    """Date after the last lesson (next unlearned day)."""
    last = get_last_lesson_date(user_id)
    return (date.fromisoformat(last) + timedelta(days=1)).isoformat()


def get_user_start_date(user_id: int) -> str:
    c = _conn()
    row = c.execute("SELECT start_date, created_at FROM users WHERE user_id=?", (user_id,)).fetchone()
    c.close()
    if row and row["start_date"]:
        return row["start_date"]
    if row and row["created_at"]:
        return row["created_at"][:10]
    return date.today().isoformat()


def get_all_lesson_dates(user_id: int) -> list:
    """All lesson dates with completion status."""
    c = _conn()
    rows = c.execute(
        "SELECT lesson_date, completed, test_score FROM daily_lessons"
        " WHERE user_id=? ORDER BY lesson_date",
        (user_id,),
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


# ── Word queries ──────────────────────────────────────────────────────────────

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
           FROM words WHERE user_id=? AND times_tested > 0
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


def get_all_words_for_export(user_id: int) -> list:
    """All words ordered by date learned — for .txt export."""
    c = _conn()
    rows = c.execute(
        "SELECT word, translation, example, date_added FROM words"
        " WHERE user_id=? ORDER BY date_added ASC, word ASC",
        (user_id,),
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_completed_lesson_count(user_id: int) -> int:
    """Number of days where user opened a lesson (for curriculum progress)."""
    c = _conn()
    count = c.execute(
        "SELECT COUNT(DISTINCT lesson_date) FROM daily_lessons WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    c.close()
    return count


def get_stats(user_id: int) -> dict:
    c = _conn()
    total = c.execute("SELECT COUNT(*) FROM words WHERE user_id=?", (user_id,)).fetchone()[0]
    done = c.execute(
        "SELECT COUNT(*) FROM daily_lessons WHERE user_id=? AND completed=1", (user_id,)
    ).fetchone()[0]
    avg = c.execute(
        "SELECT AVG(test_score * 100.0 / NULLIF(test_total, 0)) FROM daily_lessons"
        " WHERE user_id=? AND test_score IS NOT NULL AND test_total > 0",
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
