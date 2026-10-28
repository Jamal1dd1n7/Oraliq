import psycopg2
from config import DB_CONFIG

def get_connection():
    return psycopg2.connect(
        dbname=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"]
    )

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. Teachers
    cur.execute("""
    CREATE TABLE IF NOT EXISTS teachers (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE,
        full_name VARCHAR(150) NOT NULL,
        username VARCHAR(50) UNIQUE,
        password VARCHAR(255) NOT NULL
    );
    """)

    # 2. Assistants
    cur.execute("""
    CREATE TABLE IF NOT EXISTS assistants (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE,
        full_name VARCHAR(150) NOT NULL,
        username VARCHAR(50) UNIQUE
    );
    """)

    # 3. Teacher registration codes
    cur.execute("""
    CREATE TABLE IF NOT EXISTS teacher_codes (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT,
        code VARCHAR(20) UNIQUE NOT NULL,
        is_used BOOLEAN DEFAULT FALSE
    );
    """)

    # 4. Groups
    cur.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 5. Students
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id SERIAL PRIMARY KEY,
        group_id INT REFERENCES groups(id) ON DELETE CASCADE,
        full_name VARCHAR(150) NOT NULL
    );
    """)

    # 6. Schedules
    cur.execute("""
    CREATE TABLE IF NOT EXISTS schedules (
        id SERIAL PRIMARY KEY,
        teacher_id INT REFERENCES teachers(id) ON DELETE CASCADE,
        group_id INT REFERENCES groups(id) ON DELETE CASCADE,
        day_of_week VARCHAR(20) NOT NULL,
        lesson_info TEXT,
        total_weekly_lessons INT DEFAULT 0
    );
    """)

    # 7. Exams
    cur.execute("""
    CREATE TABLE IF NOT EXISTS exams (
        id SERIAL PRIMARY KEY,
        teacher_id INT REFERENCES teachers(id) ON DELETE CASCADE,
        title VARCHAR(200) NOT NULL,
        status VARCHAR(20) DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 8. Exam Questions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS exam_questions (
        id SERIAL PRIMARY KEY,
        exam_id INT REFERENCES exams(id) ON DELETE CASCADE,
        question_order INT NOT NULL,
        question_text TEXT NOT NULL
    );
    """)

    # 9. Exam Queue
    cur.execute("""
    CREATE TABLE IF NOT EXISTS exam_queue (
        id SERIAL PRIMARY KEY,
        exam_id INT REFERENCES exams(id) ON DELETE CASCADE,
        group_id INT REFERENCES groups(id) ON DELETE CASCADE,
        student_id INT REFERENCES students(id) ON DELETE CASCADE,
        student_full_name VARCHAR(150) NOT NULL,
        access_code VARCHAR(20) UNIQUE NOT NULL,
        assigned_question_ids INT[] DEFAULT '{}',
        assigned_questions_text TEXT,
        is_ready BOOLEAN DEFAULT FALSE,
        ready_timestamp TIMESTAMP,
        status VARCHAR(20) DEFAULT 'waiting',
        queue_order INT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 10. Exam Results
    cur.execute("""
    CREATE TABLE IF NOT EXISTS exam_results (
        id SERIAL PRIMARY KEY,
        exam_id INT REFERENCES exams(id) ON DELETE CASCADE,
        group_id INT REFERENCES groups(id) ON DELETE CASCADE,
        student_id INT REFERENCES students(id) ON DELETE CASCADE,
        student_full_name VARCHAR(150) NOT NULL,
        q1_text TEXT NOT NULL,
        q1_score INT CHECK (q1_score BETWEEN 1 AND 5),
        q2_text TEXT NOT NULL,
        q2_score INT CHECK (q2_score BETWEEN 1 AND 5),
        q3_text TEXT NOT NULL,
        q3_score INT CHECK (q3_score BETWEEN 1 AND 5),
        average_score NUMERIC(3, 2),
        teacher_notes TEXT,
        finished_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    cur.close()
    conn.close()