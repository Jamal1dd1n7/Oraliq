from telebot import TeleBot
from telebot.types import Message   

from telebot import types
from keyboards import teacher_main_menu, days_inline_keyboard
from database import (
    get_connection
    # get_connection, create_exam, add_batch_questions, 
    # get_teacher_exams, get_exam_question_count, get_exam_details, 
    # get_exam_questions_paginated, get_single_question, update_question_text, 
    # get_all_groups, get_group_details, start_exam_queue_batch, 
    # get_ready_students_for_teacher, save_exam_result, finish_queue_item,
    # add_group, add_batch_students
)

user_exam_states = {}
teacher_grading_state = {}
teacher_login_states = set()  # Login holatini aniq nazorat qilish uchun
group_student_states = {}

def register_teacher_handlers(bot):
    
    @bot.message_handler(func=lambda msg: msg.text == "👨‍🏫 O'qituvchi")
    def teacher_auth_prompt(message):
        teacher_login_states.add(message.from_user.id)
        bot.send_message(
            message.chat.id,
            "Iltimos, tizimga kirish uchun login va parolingizni quyidagi formatda yuboring:\n<code>login:parol</code>",
            parse_mode="HTML"
        )

    # Login filtriga faqat o'qituvchi login tugmasini bosgan bo'lsagina ishlaydigan shart qo'shildi
    @bot.message_handler(func=lambda msg: msg.from_user.id in teacher_login_states and ":" in msg.text and not msg.text.startswith("/"))
    def teacher_login_check(message):
        try:
            parts = message.text.split(":", 1)
            if len(parts) != 2:
                return
            login, password = parts[0].strip(), parts[1].strip()
            
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT id, full_name FROM teachers WHERE username = %s AND password = %s",
                (login, password)
            )
            teacher = cur.fetchone()
            cur.close()
            conn.close()

            teacher_login_states.discard(message.from_user.id)

            if teacher:
                # O'qituvchi uchun guruh qo'shish tugmasi bor maxsus klaviatura yaratamiz
                markup = teacher_main_menu()
                markup.add(types.KeyboardButton("📁 Guruhlarni boshqarish"))
                
                bot.send_message(
                    message.chat.id,
                    f"Xush kelibsiz, {teacher[1]}!",
                    reply_markup=markup
                )
            else:
                bot.send_message(message.chat.id, "Login yoki parol xato! Qaytadan urinib ko'ring.")
        except Exception:
            pass

    @bot.message_handler(func=lambda msg: msg.text == "📅 Dars jadvali")
    def teacher_schedule(message):
        bot.send_message(
            message.chat.id,
            "Hafta kunini tanlang:",
            reply_markup=days_inline_keyboard()
        )