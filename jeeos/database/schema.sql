CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    exam_year INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS study_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    start_time TEXT NOT NULL,
    end_time TEXT,
    subject TEXT NOT NULL,
    chapter TEXT NOT NULL,
    questions_solved INTEGER DEFAULT 0,
    duration_minutes REAL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS syllabus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    chapter TEXT NOT NULL,
    total_weight INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS syllabus_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    syllabus_id INTEGER,
    completion_status INTEGER DEFAULT 0,
    confidence_score REAL DEFAULT 0,
    questions_solved INTEGER DEFAULT 0,
    accuracy REAL DEFAULT 0,
    last_revision_date TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (syllabus_id) REFERENCES syllabus(id)
);

CREATE TABLE IF NOT EXISTS mock_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    test_name TEXT NOT NULL,
    test_date TEXT NOT NULL,
    physics_score REAL NOT NULL,
    chemistry_score REAL NOT NULL,
    math_score REAL NOT NULL,
    total_score REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS question_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    year INTEGER NOT NULL,
    subject TEXT NOT NULL,
    chapter TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    time_taken_seconds INTEGER NOT NULL,
    attempt_date TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS mistake_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    question_image_path TEXT,
    chapter TEXT NOT NULL,
    mistake_type TEXT CHECK(mistake_type IN ('concept','calculation','careless','time pressure')),
    note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS revision_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    chapter TEXT NOT NULL,
    due_date TEXT NOT NULL,
    interval_day INTEGER NOT NULL,
    completed INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS daily_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    plan_date TEXT NOT NULL,
    task TEXT NOT NULL,
    subject TEXT,
    chapter TEXT,
    task_type TEXT,
    target TEXT,
    completed INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    habit_date TEXT NOT NULL,
    woke_on_time INTEGER DEFAULT 0,
    completed_sessions INTEGER DEFAULT 0,
    no_phone_usage INTEGER DEFAULT 0,
    did_revision INTEGER DEFAULT 0,
    solved_pyq INTEGER DEFAULT 0,
    exercise INTEGER DEFAULT 0,
    slept_on_time INTEGER DEFAULT 0,
    discipline_score REAL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    metric_date TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
