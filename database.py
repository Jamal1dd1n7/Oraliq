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


# --- O'QITUVCHI VA AUTENTIFIKASIYA FUNKSIYALARI ---
def check_teacher_by_telegram_id(telegram_id):
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

# --- IMTIHON VA SAVOLLAR FUNKSIYALARI ---
def create_exam(teacher_telegram_id, title):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM teachers WHERE telegram_id = %s", (teacher_telegram_id,))
        t = cur.fetchone()
        if not t:
            return None
        
        cur.execute(
            "INSERT INTO exams (teacher_id, title, status) VALUES (%s, %s, 'active') RETURNING id",
            (t[0], title)
        )
        row = cur.fetchone()
        conn.commit()
        return row[0] if row else None
    except Exception as e:
        conn.rollback()
        print(f"Xatolik create_exam: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def add_batch_questions(exam_id, questions_list):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM exam_questions WHERE exam_id = %s", (exam_id,))
        res = cur.fetchone()
        current_count = res[0] if res else 0 
        
        inserted = 0
        for q_text in questions_list:
            if current_count + inserted >= 120:
                break
            inserted += 1
            cur.execute(
                "INSERT INTO exam_questions (exam_id, question_order, question_text) VALUES (%s, %s, %s)",
                (exam_id, current_count + inserted, q_text.strip())
            )
        
        conn.commit()
        return current_count + inserted
    except Exception as e:
        conn.rollback()
        print(f"Xatolik add_batch_questions: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def get_teacher_exams(teacher_telegram_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT e.id, e.title, e.status, COUNT(q.id) as question_count
            FROM exams e
            JOIN teachers t ON e.teacher_id = t.id
            LEFT JOIN exam_questions q ON e.id = q.exam_id
            WHERE t.telegram_id = %s
            GROUP BY e.id, e.title, e.status
            ORDER BY e.created_at DESC
        """, (teacher_telegram_id,))
        return cur.fetchall()
    except Exception as e:
        print(f"Xatolik get_teacher_exams: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_exam_question_count(exam_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM exam_questions WHERE exam_id = %s", (exam_id,))
        res = cur.fetchone()
        return res[0] if res else 0
    except Exception as e:
        print(f"Xatolik get_exam_question_count: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def get_exam_details(exam_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, title, status FROM exams WHERE id = %s", (exam_id,))
        return cur.fetchone()
    except Exception as e:
        print(f"Xatolik get_exam_details: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def get_exam_questions_paginated(exam_id, limit=10, offset=0):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, question_order, question_text 
            FROM exam_questions 
            WHERE exam_id = %s 
            ORDER BY question_order ASC 
            LIMIT %s OFFSET %s
        """, (exam_id, limit, offset))
        return cur.fetchall()
    except Exception as e:
        print(f"Xatolik get_exam_questions_paginated: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_single_question(question_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, question_order, question_text FROM exam_questions WHERE id = %s", (question_id,))
        return cur.fetchone()
    except Exception as e:
        print(f"Xatolik get_single_question: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def update_question_text(question_id, new_text):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE exam_questions SET question_text = %s WHERE id = %s", (new_text, question_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Xatolik update_question_text: {e}")
    finally:
        cur.close()
        conn.close()

def get_exam_questions_list(exam_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, question_text FROM exam_questions WHERE exam_id = %s", (exam_id,))
        return cur.fetchall()
    except Exception as e:
        print(f"Xatolik get_exam_questions_list: {e}")
        return []
    finally:
        cur.close()
        conn.close()

# --- GURUH VA TALABALAR FUNKSIYALARI ---
def add_group(name):
    """Yangi guruh yaratish va ID sini qaytarish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO groups (name) VALUES (%s) RETURNING id", (name,))
        row = cur.fetchone()
        conn.commit()
        return row[0] if row else None
    except Exception as e:
        conn.rollback()
        print(f"Xatolik add_group: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def add_batch_students(group_id, students_list):
    """Guruhga talabalarni to'plam ko'rinishida qo'shish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        inserted = 0
        for student_name in students_list:
            cur.execute("""
                INSERT INTO students (group_id, full_name) 
                VALUES (%s, %s)
            """, (group_id, student_name))
            inserted += 1
            
        conn.commit()
        return inserted
    except Exception as e:
        conn.rollback()
        print(f"Xatolik add_batch_students: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def get_group_details(group_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM groups WHERE id = %s", (group_id,))
        g = cur.fetchone()
        
        cur.execute("SELECT COUNT(*) FROM students WHERE group_id = %s", (group_id,))
        res = cur.fetchone()
        count = res[0] if res else 0
        
        return g, count
    except Exception as e:
        print(f"Xatolik get_group_details: {e}")
        return None, 0
    finally:
        cur.close()
        conn.close()

def get_group_students(group_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, full_name FROM students WHERE group_id = %s ORDER BY id ASC", (group_id,))
        return cur.fetchall()
    except Exception as e:
        print(f"Xatolik get_group_students: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_all_groups():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM groups ORDER BY id ASC")
        return cur.fetchall()
    except Exception as e:
        print(f"Xatolik get_all_groups: {e}")
        return []
    finally:
        cur.close()
        conn.close()
    
# --- IMTIHON NAVBATI VA NATIJALAR FUNKSIYALARI ---
def start_exam_queue_batch(exam_id, group_id):
    import random
    conn = get_connection()
    cur = conn.cursor()
    try:
        students = get_group_students(group_id)
        if not students:
            return []
        
        all_questions = get_exam_questions_list(exam_id)
        if len(all_questions) < 3:
            return "not_enough_questions"
        
        first_five = students[:5]
        queue_results = []
        
        for index, (student_id, student_name) in enumerate(first_five):
            selected_qs = random.sample(all_questions, 3)
            q_ids = [q[0] for q in selected_qs]
            q_texts = "\n".join([f"{i+1}. {q[1]}" for i, q in enumerate(selected_qs)])
            
            access_code = f"ST-{random.randint(1000, 9999)}"
            
            cur.execute("""
                INSERT INTO exam_queue (exam_id, group_id, student_id, student_full_name, access_code, assigned_question_ids, assigned_questions_text, queue_order, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'waiting')
            """, (exam_id, group_id, student_id, student_name, access_code, q_ids, q_texts, index + 1))
            
            queue_results.append({
                "name": student_name,
                "code": access_code
            })
        
        conn.commit()
        return queue_results
    except Exception as e:
        conn.rollback()
        print(f"Xatolik start_exam_queue_batch: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_queue_by_code(access_code):
    """Kirish kodi bo'yicha navbatdagi talaba ma'lumotlarini olish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, exam_id, group_id, student_id, student_full_name, 
                   assigned_questions_text, is_ready, status, queue_order 
            FROM exam_queue 
            WHERE access_code = %s
        """, (access_code,))
        return cur.fetchone()
    except Exception as e:
        print(f"Xatolik get_queue_by_code: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def check_previous_student_finished(exam_id, group_id, current_queue_order):
    """Joriy talabadan oldingi talaba imtihonni tugatganligini tekshirish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*) FROM exam_queue 
            WHERE exam_id = %s AND group_id = %s AND queue_order < %s AND status != 'finished'
        """, (exam_id, group_id, current_queue_order))
        row = cur.fetchone()
        unfinished_count = row[0] if row else 0
        return unfinished_count == 0  # Agar oldidagilarning hammasi finished bo'lsa True qaytaradi
    except Exception as e:
        print(f"Xatolik check_previous_student_finished: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def set_student_ready_status(queue_id):
    """Talaba tayyor tugmasini bosganda statusni yangilash"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE exam_queue 
            SET is_ready = TRUE, status = 'ready', ready_timestamp = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (queue_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Xatolik set_student_ready_status: {e}")
    finally:
        cur.close()
        conn.close()

def get_student_exam_result(exam_id, student_id):
    """Imtihon tugagach talabaning natijasini olish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT q1_text, q1_score, q2_text, q2_score, q3_text, q3_score, average_score, teacher_notes 
            FROM exam_results 
            WHERE exam_id = %s AND student_id = %s
        """, (exam_id, student_id))
        return cur.fetchone()
    except Exception as e:
        print(f"Xatolik get_student_exam_result: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def get_ready_students_for_teacher(teacher_telegram_id):
    """O'qituvchining imtihoni uchun 'ready' statusidagi navbatdagi tayyor talabani olish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT q.id, q.student_full_name, q.assigned_questions_text, q.exam_id, q.group_id, q.student_id
            FROM exam_queue q
            JOIN exams e ON q.exam_id = e.id
            JOIN teachers t ON e.teacher_id = t.id
            WHERE t.telegram_id = %s AND q.status = 'ready'
            ORDER BY q.ready_timestamp ASC
            LIMIT 1
        """, (teacher_telegram_id,))
        return cur.fetchone()
    except Exception as e:
        print(f"Xatolik get_ready_students_for_teacher: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def save_exam_result(exam_id, group_id, student_id, student_name, q1_text, q1_score, q2_text, q2_score, q3_text, q3_score):
    """Talabaning imtihon natijalarini saqlash va o'rtacha ballni qaytarish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        avg_score = round((q1_score + q2_score + q3_score) / 3.0, 2)
        
        cur.execute("""
            INSERT INTO exam_results (exam_id, group_id, student_id, student_full_name, q1_text, q1_score, q2_text, q2_score, q3_text, q3_score, average_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (exam_id, group_id, student_id, student_name, q1_text, q1_score, q2_text, q2_score, q3_text, q3_score, avg_score))
        
        conn.commit()
        return avg_score
    except Exception as e:
        conn.rollback()
        print(f"Xatolik save_exam_result: {e}")
        return 0.0
    finally:
        cur.close()
        conn.close()

def finish_queue_item(queue_id):
    """Navbatdagi talaba imtihonni tugatgach statusini 'finished' qilish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE exam_queue SET status = 'finished' WHERE id = %s", (queue_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Xatolik finish_queue_item: {e}")
    finally:
        cur.close()
        conn.close()        

def update_queue_student_telegram_id(queue_id, telegram_id):
    """Talaba kodni kiritganda uning telegram_id sini navbatga yozib qo'yish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE exam_queue SET student_telegram_id = %s WHERE id = %s", (telegram_id, queue_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Xatolik update_queue_student_telegram_id: {e}")
    finally:
        cur.close()
        conn.close()

def add_next_student_to_queue(exam_id, group_id):
    """Bitta talaba tugatgandan so'ng, guruhdagi keyingi talabani navbatga qo'shish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # 1. Guruhdagi barcha talabalarni olamiz
        students = get_group_students(group_id)
        if not students:
            return None
            
        # 2. Bu imtihonda allaqachon navbatga qo'shilgan student_id larni topamiz
        cur.execute("SELECT student_id FROM exam_queue WHERE exam_id = %s AND group_id = %s", (exam_id, group_id))
        existing_student_ids = {row[0] for row in cur.fetchall()}
        
        # 3. Hali navbatga tushmagan birinchi talabani topamiz
        next_student = None
        for s_id, s_name in students:
            if s_id not in existing_student_ids:
                next_student = (s_id, s_name)
                break
                
        if not next_student:
            return None # Barcha talabalar imtihondan o'tgan
            
        student_id, student_name = next_student
        
        # 4. Eng oxirgi queue_order ni aniqlaymiz
        cur.execute("SELECT MAX(queue_order) FROM exam_queue WHERE exam_id = %s AND group_id = %s", (exam_id, group_id))
        row = cur.fetchone()
        max_order = row[0] if row and row[0] is not None else 0
        new_order = max_order + 1
        
        # 5. Savollardan 3 tasini tasodifiy tanlaymiz
        all_questions = get_exam_questions_list(exam_id)
        if len(all_questions) < 3:
            return None
            
        import random
        selected_qs = random.sample(all_questions, 3)
        q_ids = [q[0] for q in selected_qs]
        q_texts = "\n".join([f"{i+1}. {q[1]}" for i, q in enumerate(selected_qs)])
        access_code = f"ST-{random.randint(1000, 9999)}"
        
        # 6. Yangi talabani navbatga yozamiz
        cur.execute("""
            INSERT INTO exam_queue (exam_id, group_id, student_id, student_full_name, access_code, assigned_question_ids, assigned_questions_text, queue_order, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'waiting')
        """, (exam_id, group_id, student_id, student_name, access_code, q_ids, q_texts, new_order))
        
        conn.commit()
        return {"name": student_name, "code": access_code}
    except Exception as e:
        conn.rollback()
        print(f"Xatolik add_next_student_to_queue: {e}")
        return None
    finally:
        cur.close()
        conn.close()        