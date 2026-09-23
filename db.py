"""
Lightweight database layer using Python's built-in sqlite3 module.
No extra ORM dependency required.
"""
import sqlite3
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "skillgappath.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        age INTEGER,
        profession TEXT,
        phone TEXT,
        username TEXT UNIQUE NOT NULL,
        email TEXT,
        location TEXT DEFAULT 'India',
        password_hash TEXT NOT NULL DEFAULT '',
        firebase_uid TEXT,
        security_question TEXT,
        security_answer_hash TEXT,
        avatar_path TEXT,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        skill_id TEXT NOT NULL,
        started_at TEXT NOT NULL,
        hours_per_week INTEGER DEFAULT 5,
        syllabus_source TEXT DEFAULT 'general',
        syllabus_name TEXT DEFAULT '',
        syllabus_summary TEXT DEFAULT '',
        roadmap_json TEXT DEFAULT '[]',
        diagnostic_json TEXT DEFAULT '[]',
        level TEXT DEFAULT 'basic',
        level_score REAL DEFAULT 0,
        level_reason TEXT DEFAULT '',
        FOREIGN KEY (user_id) REFERENCES users (id)
    );

    CREATE TABLE IF NOT EXISTS topic_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        skill_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        mastered INTEGER DEFAULT 0,
        quiz_score REAL DEFAULT 0.0,
        source TEXT DEFAULT 'cold_start',
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );

    CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        activity_date TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id),
        UNIQUE(user_id, activity_date)
    );

    CREATE TABLE IF NOT EXISTS user_preferences (
        user_id INTEGER PRIMARY KEY,
        learning_goal TEXT DEFAULT '',
        hours_per_week INTEGER DEFAULT 5,
        learning_style TEXT DEFAULT 'mixed',
        learning_focus TEXT DEFAULT '',
        theme TEXT DEFAULT 'system',
        reminders INTEGER DEFAULT 1,
        streak_alerts INTEGER DEFAULT 1,
        product_updates INTEGER DEFAULT 0,
        auto_next INTEGER DEFAULT 1,
        show_completed INTEGER DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        topic TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT DEFAULT 'open',
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)
    # Lightweight migrations for databases created by earlier Learnora versions.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "avatar_path" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN avatar_path TEXT")
    if "firebase_uid" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN firebase_uid TEXT")

    # Adaptive-learning enrollment migrations. Existing databases receive the
    # new columns without losing current enrollments.
    enrollment_columns = {row[1] for row in conn.execute("PRAGMA table_info(enrollments)").fetchall()}
    migrations = {
        "syllabus_source": "ALTER TABLE enrollments ADD COLUMN syllabus_source TEXT DEFAULT 'general'",
        "syllabus_name": "ALTER TABLE enrollments ADD COLUMN syllabus_name TEXT DEFAULT ''",
        "syllabus_summary": "ALTER TABLE enrollments ADD COLUMN syllabus_summary TEXT DEFAULT ''",
        "roadmap_json": "ALTER TABLE enrollments ADD COLUMN roadmap_json TEXT DEFAULT '[]'",
        "diagnostic_json": "ALTER TABLE enrollments ADD COLUMN diagnostic_json TEXT DEFAULT '[]'",
        "level": "ALTER TABLE enrollments ADD COLUMN level TEXT DEFAULT 'basic'",
        "level_score": "ALTER TABLE enrollments ADD COLUMN level_score REAL DEFAULT 0",
        "level_reason": "ALTER TABLE enrollments ADD COLUMN level_reason TEXT DEFAULT ''",
    }
    for column, sql in migrations.items():
        if column not in enrollment_columns:
            conn.execute(sql)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid) WHERE firebase_uid IS NOT NULL")
    conn.commit()
    conn.close()


def now():
    return datetime.utcnow().isoformat()


def today():
    return datetime.utcnow().strftime("%Y-%m-%d")
