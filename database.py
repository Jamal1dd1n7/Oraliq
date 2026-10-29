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
    
    # 1. Teachers (O'qituvchilar)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS teachers (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE,
        full_name VARCHAR(150) NOT NULL,
        username VARCHAR(50) UNIQUE,
        password VARCHAR(255) NOT NULL
    );
    """)

    # 2. Assistants (Yordamchilar)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS assistants (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE,
        full_name VARCHAR(150) NOT NULL,
        username VARCHAR(50) UNIQUE
    );
    """)

    # 3. Teacher registration codes (O'qituvchilarni ro'yxatdan o'tkazish kodlari - Yangi arxitektura)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS teacher_codes (
        id SERIAL PRIMARY KEY,
        first_name VARCHAR(100),
        telegram_id BIGINT,
        code VARCHAR(20) UNIQUE NOT NULL,
        status VARCHAR(20) DEFAULT 'yangi'
    );
    """)

    # 4. Groups (Guruhlar)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 5. Students (Talabalar)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id SERIAL PRIMARY KEY,
        group_id INT REFERENCES groups(id) ON DELETE CASCADE,
        full_name VARCHAR(150) NOT NULL,
        telegram_id BIGINT UNIQUE
    );
    """)

    # 6. Schedules (Dars jadvali)
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

    # 7. Exams (Imtihonlar)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS exams (
        id SERIAL PRIMARY KEY,
        teacher_id INT REFERENCES teachers(id) ON DELETE CASCADE,
        title VARCHAR(200) NOT NULL,
        status VARCHAR(20) DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 8. Exam Questions (Imtihon savollari)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS exam_questions (
        id SERIAL PRIMARY KEY,
        exam_id INT REFERENCES exams(id) ON DELETE CASCADE,
        question_order INT NOT NULL,
        question_text TEXT NOT NULL
    );
    """)

    # 9. Exam Queue (Imtihon navbati va jarayoni)
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

    # 10. Exam Results (Imtihon natijalari)
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


# --- YANGI ARXITEKTURA UCHUN DB FUNKSIYALARI ---

def check_teacher_by_telegram_id(telegram_id):
    """Telegram ID orqali teachers jadvalidan qidirish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, full_name, username FROM teachers WHERE telegram_id = %s", (telegram_id,))
        return cur.fetchone()
    except Exception as e:
        print(f"Xatolik check_teacher_by_telegram_id: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def add_pending_teacher(first_name, telegram_id, code):
    """O'qituvchi ismini kiritganda teacher_codes ga 'yangi' statusi bilan yozish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM teacher_codes WHERE telegram_id = %s", (telegram_id,))
        existing = cur.fetchone()
        
        if existing:
            cur.execute("""
                UPDATE teacher_codes 
                SET first_name = %s, code = %s, status = 'yangi' 
                WHERE telegram_id = %s
            """, (first_name, code, telegram_id))
        else:
            cur.execute("""
                INSERT INTO teacher_codes (first_name, telegram_id, code, status)
                VALUES (%s, %s, %s, 'yangi')
            """, (first_name, telegram_id, code))
            
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Xatolik add_pending_teacher: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_pending_teacher_by_code(code):
    """Admin kiritgan kod bo'yicha 'yangi' statusli o'qituvchini topish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, first_name, telegram_id, code, status 
            FROM teacher_codes 
            WHERE code = %s AND status = 'yangi'
        """, (code,))
        return cur.fetchone()
    except Exception as e:
        print(f"Xatolik get_pending_teacher_by_code: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def complete_teacher_registration(telegram_id, full_name, username, password, code):
    """Admin ma'lumotlarni kiritgach, teachers ga yozish va teacher_codes statusini 'tasdiqlangan' qilish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO teachers (full_name, username, password, telegram_id)
            VALUES (%s, %s, %s, %s) RETURNING id
        """, (full_name, username, password, telegram_id))
        
        row = cur.fetchone()
        teacher_id = row[0] if row else None

        cur.execute("""
            UPDATE teacher_codes 
            SET status = 'tasdiqlangan' 
            WHERE code = %s
        """, (code,))

        conn.commit()
        return teacher_id
    except Exception as e:
        conn.rollback()
        print(f"Xatolik complete_teacher_registration: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def verify_teacher_login(username, password):
    """Login va parol orqali o'qituvchini tekshirish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, full_name FROM teachers WHERE username = %s AND password = %s", (username, password))
        return cur.fetchone()
    except Exception as e:
        print(f"Xatolik verify_teacher_login: {e}")
        return None
    finally:
        cur.close()
        conn.close()