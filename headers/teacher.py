import random
from telebot import types
from keyboards import teacher_main_menu
from database import *

# Holatlarni boshqarish uchun lug'atlar va setlar
teacher_name_states = set()
teacher_login_step = set()        # Login kiritishini kutayotganlar
teacher_password_step = {}        # {telegram_id: login} - parolni kutayotganlar va ularning loginlari
user_exam_states = {}
teacher_grading_state = {}
group_student_states = {}
user_exam_process = {}
teacher_grading_states = {}

def register_teacher_handlers(bot):
    
    @bot.message_handler(func=lambda msg: msg.text == "👨‍🏫 O'qituvchi")
    def teacher_entry_point(message):
        telegram_id = message.from_user.id
        
        teacher = check_teacher_by_telegram_id(telegram_id)
        if teacher:
            teacher_login_step.add(telegram_id)
            bot.send_message(
                message.chat.id,
                "Sizning profilingiz mavjud.\n\n"
                "Iltimos, tizimga kirish uchun <b>loginingizni</b> kiriting:",
                parse_mode="HTML"
            )
        else:
            teacher_name_states.add(telegram_id)
            bot.send_message(
                message.chat.id,
                "❌ Siz bazada yo'qsiz.\n"
                "O'qituvchilar qatoriga qo'shilish uchun <b>ismingizni</b> kiriting:",
                parse_mode="HTML"
            )

    @bot.message_handler(func=lambda msg: msg.from_user.id in teacher_name_states and not msg.text.startswith("/"))
    def process_teacher_name(message):
        telegram_id = message.from_user.id
        first_name = message.text.strip()
        
        code = f"TCH-{random.randint(1000, 9999)}"
        success = add_pending_teacher(first_name, telegram_id, code)
        teacher_name_states.discard(telegram_id)
        
        if success:
            bot.send_message(
                message.chat.id,
                f"✅ Ma'lumotlaringiz qabul qilindi!\n\n"
                f"Sizning ro'yxatdan o'tish kodingiz: <code>{code}</code>\n"
                f"Iltimos, admin tasdiqlashini kuting. Admin kodni kiritgandan so'ng sizga login va parol beriladi.",
                parse_mode="HTML"
            )
        else:
            bot.send_message(message.chat.id, "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

    @bot.message_handler(func=lambda msg: msg.from_user.id in teacher_login_step and not msg.text.startswith("/"))
    def process_teacher_login_input(message):
        telegram_id = message.from_user.id
        login = message.text.strip()
        
        teacher_login_step.discard(telegram_id)
        teacher_password_step[telegram_id] = login
        
        bot.send_message(
            message.chat.id,
            "🔑 Endi <b>parolingizni</b> kiriting:",
            parse_mode="HTML"
        )

    @bot.message_handler(func=lambda msg: msg.from_user.id in teacher_password_step and not msg.text.startswith("/"))
    def process_teacher_password_input(message):
        telegram_id = message.from_user.id
        password = message.text.strip()
        
        login = teacher_password_step.pop(telegram_id, None)
        
        if not login:
            bot.send_message(message.chat.id, "❌ Xatolik yuz berdi. Iltimos, qaytadan /start bosing.")
            return

        teacher = verify_teacher_login(login, password)
        
        if teacher:
            teacher_id, full_name = teacher
            bot.send_message(
                message.chat.id,
                f"✅ Xush kelibsiz, ustoz <b>{full_name}</b>!",
                reply_markup=teacher_main_menu(),
                parse_mode="HTML"
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ Login yoki parol xato!\n"
                "Qaytadan urinib ko'rish uchun /start buyrug'ini bosing."
            )

    # --- IMTIHON YARATISH VA BOSHQARISH ---
    @bot.message_handler(func=lambda msg: msg.text == "📝 Imtihon")
    def exam_main_menu(message):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(
            types.KeyboardButton("➕ Yangi imtihon yaratish"),
            types.KeyboardButton("📋 Imtihonlar jadvali"),
            types.KeyboardButton("🔙 Asosiy menyu")
        )
        bot.send_message(
            message.chat.id,
            "📝 <b>Imtihon bo'limi:</b>\nKerakli amalni tanlang:",
            reply_markup=markup,
            parse_mode="HTML"
        )

    @bot.message_handler(func=lambda msg: msg.text == "➕ Yangi imtihon yaratish")
    def start_create_exam(message):
        msg = bot.send_message(
            message.chat.id,
            "Iltimos, yaratilayotgan <b>imtihon nomini</b> kiriting:",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, process_exam_title)

    def process_exam_title(message):
        title = message.text.strip()
        telegram_id = message.from_user.id
        
        exam_id = create_exam(telegram_id, title)
        if not exam_id:
            bot.send_message(message.chat.id, "❌ Imtihon yaratishda xatolik yuz berdi.")
            return
        
        user_exam_states[telegram_id] = {"exam_id": exam_id, "title": title}
        
        bot.send_message(
            message.chat.id,
            f"✅ Imtihon nomi: <b>{title}</b> qabul qilindi.\n\n"
            f"Endi savollarni quyidagi ko'rinishda bitta xabarda yuboring:\n\n"
            f"<code>1) Savol matni 1?\n2) Savol matni 2?\n...</code>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(message, process_exam_questions)

    def process_exam_questions(message):
        telegram_id = message.from_user.id
        if telegram_id not in user_exam_states:
            return
        
        exam_id = user_exam_states[telegram_id]["exam_id"]
        text = message.text.strip()
        
        if text.lower() in ["tayyor", "✅ tayyor"]:
            finish_exam_creation(message)
            return

        lines = text.split("\n")
        questions_list = [line.strip() for line in lines if line.strip()]
        
        if not questions_list:
            msg = bot.send_message(message.chat.id, "❌ Savollar topilmadi. Qaytadan yuboring:")
            bot.register_next_step_handler(msg, process_exam_questions)
            return

        total_saved = add_batch_questions(exam_id, questions_list)
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton("➕ Yana savol qo'shish"),
            types.KeyboardButton("✅ Tayyor")
        )
        
        bot.send_message(
            message.chat.id,
            f"✅ Qabul qilindi! Jami savollar soni: <b>{total_saved} ta</b>.\n\nYana savol qo'shasizmi yoki tugatasizmi?",
            reply_markup=markup,
            parse_mode="HTML"
        )
        bot.register_next_step_handler(message, process_after_batch)

    def process_after_batch(message):
        text = message.text.strip()
        if text == "➕ Yana savol qo'shish":
            bot.send_message(message.chat.id, "Keyingi savollar to'plamini yuboring:")
            bot.register_next_step_handler(message, process_exam_questions)
        elif text == "✅ Tayyor":
            finish_exam_creation(message)
        else:
            bot.send_message(message.chat.id, "Iltimos, tugmalardan birini tanlang:")
            bot.register_next_step_handler(message, process_after_batch)

    def finish_exam_creation(message):
        telegram_id = message.from_user.id
        if telegram_id in user_exam_states:
            exam_data = user_exam_states.pop(telegram_id)
            exam_id = exam_data["exam_id"]
            count = get_exam_question_count(exam_id)
            
            markup = teacher_main_menu()
            
            bot.send_message(
                message.chat.id,
                f"🎉 Imtihon muvaffaqiyatli yaratildi!\n\n📌 Nomi: <b>{exam_data['title']}</b>\n❓ Jami savollar: {count} ta",
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            bot.send_message(message.chat.id, "Imtihon yaratish yakunlandi.", reply_markup=teacher_main_menu())

    # --- IMTIHONLAR JADVALI VA SAHIFALASH ---
    @bot.message_handler(func=lambda msg: msg.text == "📋 Imtihonlar jadvali")
    def show_exams_schedule(message):
        telegram_id = message.from_user.id
        exams = get_teacher_exams(telegram_id)
        
        if not exams:
            bot.send_message(message.chat.id, "❌ Hozircha yaratilgan imtihonlar yo'q.")
            return
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for e_id, title, status, q_count in exams:
            icon = "✅" if status == "finished" else "❌"
            markup.add(types.InlineKeyboardButton(f"{icon} {title} ({q_count} ta savol)", callback_data=f"exam_detail_{e_id}"))
        
        bot.send_message(message.chat.id, "📋 <b>Sizning imtihonlaringiz jadvali:</b>", reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("exam_detail_"))
    def exam_detail_callback(call):
        exam_id = int(call.data.split("_")[2])
        bot.answer_callback_query(call.id)
        
        exam = get_exam_details(exam_id)
        if not exam:
            return
        
        _, title, status = exam
        q_count = get_exam_question_count(exam_id)
        icon = "Olingan ✅" if status == "finished" else "Olinmagan ❌"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("👁 Savollarni ko'rish", callback_data=f"view_q_{exam_id}_0"),
            types.InlineKeyboardButton("✏️ Savollarni tahrirlash", callback_data=f"edit_q_{exam_id}_0"),
        )
        markup.add(
            types.InlineKeyboardButton("🚀 Imtihon olish", callback_data=f"start_exam_{exam_id}"),
            types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_exams_list")
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📌 <b>Imtihon:</b> {title}\n📊 <b>Holati:</b> {icon}\n❓ <b>Savollar soni:</b> {q_count} ta",
            reply_markup=markup,
            parse_mode="HTML"
        )

    @bot.callback_query_handler(func=lambda call: call.data == "back_to_exams_list")
    def back_to_exams_callback(call):
        bot.answer_callback_query(call.id)
        show_exams_schedule(call.message)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("view_q_"))
    def view_questions_callback(call):
        parts = call.data.split("_")
        exam_id = int(parts[2])
        offset = int(parts[3])
        bot.answer_callback_query(call.id)
        
        questions = get_exam_questions_paginated(exam_id, limit=10, offset=offset)
        total_count = get_exam_question_count(exam_id)
        
        text = f"📖 <b>Savollar ro'yxati ({offset+1}-{min(offset+10, total_count)} / {total_count}):</b>\n\n"
        markup = types.InlineKeyboardMarkup(row_width=5)
        
        row_buttons = []
        for q_id, q_order, q_text in questions:
            text += f"<b>{q_order}.</b> {q_text[:50]}...\n"
            row_buttons.append(types.InlineKeyboardButton(str(q_order), callback_data=f"single_q_{q_id}"))
        
        for i in range(0, len(row_buttons), 5):
            markup.row(*row_buttons[i:i+5])
        
        nav_buttons = []
        if offset >= 10:
            nav_buttons.append(types.InlineKeyboardButton("⬅️ Oldingi", callback_data=f"view_q_{exam_id}_{offset-10}"))
        if offset + 10 < total_count:
            nav_buttons.append(types.InlineKeyboardButton("Keyingi ➡️", callback_data=f"view_q_{exam_id}_{offset+10}"))
        if nav_buttons:
            markup.row(*nav_buttons)
            
        markup.row(types.InlineKeyboardButton("🔙 Orqaga", callback_data=f"exam_detail_{exam_id}"))
        
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("single_q_"))
    def single_question_callback(call):
        q_id = int(call.data.split("_")[2])
        bot.answer_callback_query(call.id)
        q = get_single_question(q_id)
        if q:
            bot.send_message(call.message.chat.id, f"❓ <b>{q[1]}-savol:</b>\n\n{q[2]}", parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("edit_q_"))
    def edit_questions_callback(call):
        parts = call.data.split("_")
        exam_id = int(parts[2])
        offset = int(parts[3])
        bot.answer_callback_query(call.id)
        
        questions = get_exam_questions_paginated(exam_id, limit=10, offset=offset)
        total_count = get_exam_question_count(exam_id)
        
        text = f"✏️ <b>Tahrirlash uchun savolni tanlang ({offset+1}-{min(offset+10, total_count)} / {total_count}):</b>\n"
        markup = types.InlineKeyboardMarkup(row_width=5)
        
        row_buttons = [types.InlineKeyboardButton(str(q_order), callback_data=f"select_edit_{q_id}") for q_id, q_order, _ in questions]
        for i in range(0, len(row_buttons), 5):
            markup.row(*row_buttons[i:i+5])
            
        nav_buttons = []
        if offset >= 10:
            nav_buttons.append(types.InlineKeyboardButton("⬅️ Oldingi", callback_data=f"edit_q_{exam_id}_{offset-10}"))
        if offset + 10 < total_count:
            nav_buttons.append(types.InlineKeyboardButton("Keyingi ➡️", callback_data=f"edit_q_{exam_id}_{offset+10}"))
        if nav_buttons:
            markup.row(*nav_buttons)
            
        markup.row(types.InlineKeyboardButton("🔙 Orqaga", callback_data=f"exam_detail_{exam_id}"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("select_edit_"))
    def select_edit_callback(call):
        q_id = int(call.data.split("_")[2])
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "📝 Ushbu savolni tahrirlash uchun <b>yangi matnini</b> yuboring:", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_update_question_text, q_id)

    def process_update_question_text(message, q_id):
        update_question_text(q_id, message.text.strip())
        bot.send_message(message.chat.id, "✅ Savol muvaffaqiyatli tahrirlandi!", reply_markup=teacher_main_menu())

    # --- IMTIHON OLISH BOSQICHLARI ---
    @bot.callback_query_handler(func=lambda call: call.data.startswith("start_exam_"))
    def handle_start_exam_click(call):
        exam_id = int(call.data.split("_")[2])
        telegram_id = call.from_user.id
        
        user_exam_process[telegram_id] = {"exam_id": exam_id}

        groups = get_all_groups()
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        if groups:
            for g_id, g_name in groups:
                markup.add(types.InlineKeyboardButton(f"👥 {g_name}", callback_data=f"select_group_{g_id}"))
        
        markup.add(types.InlineKeyboardButton("➕ Yangi guruh qo'shish", callback_data="add_new_group"))
        markup.add(types.InlineKeyboardButton("🔙 Ortga", callback_data=f"exam_detail_{exam_id}"))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="👥 <b>Imtihon olinadigan guruhni tanlang:</b>\n\n"
                 "Agar kerakli guruh ro'yxatda bo'lmasa, yangi guruh qo'shing:",
            reply_markup=markup,
            parse_mode="HTML"
        )

    @bot.callback_query_handler(func=lambda call: call.data == "add_new_group")
    def handle_add_group_click(call):
        msg = bot.send_message(
            call.message.chat.id,
            "📝 Yangi <b>guruh nomini</b> kiriting (masalan: <i>210-guruh</i>):",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, process_group_name)

    def process_group_name(message):
        group_name = message.text.strip()
        telegram_id = message.from_user.id
        
        if telegram_id not in user_exam_process:
            user_exam_process[telegram_id] = {}
            
        user_exam_process[telegram_id]["new_group_name"] = group_name

        msg = bot.send_message(
            message.chat.id,
            f"✅ Guruh nomi: <b>{group_name}</b>\n\n"
            f"Endi ushbu guruh talabalari ro'yxatini quyidagi ko'rinishda bitta xabarda yuboring:\n\n"
            f"<code>1. Xolmatov Jamoliddin\n2. Yakubov Javohir\n3. Qodirov Ali</code>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, process_group_students)

    def process_group_students(message):
        telegram_id = message.from_user.id
        text = message.text.strip()
        
        if telegram_id not in user_exam_process or "new_group_name" not in user_exam_process[telegram_id]:
            bot.send_message(message.chat.id, "❌ Seans vaqti tugadi. Qaytadan urinib ko'ring.")
            return

        group_name = user_exam_process[telegram_id]["new_group_name"]
        
        lines = text.split("\n")
        students_list = []
        for line in lines:
            cleaned = line.strip()
            if cleaned:
                if "." in cleaned and cleaned.split(".", 1)[0].isdigit():
                    cleaned = cleaned.split(".", 1)[1].strip()
                elif ")" in cleaned and cleaned.split(")", 1)[0].isdigit():
                    cleaned = cleaned.split(")", 1)[1].strip()
                students_list.append(cleaned)

        if not students_list:
            msg = bot.send_message(message.chat.id, "❌ Talabalar topilmadi. Qaytadan yuboring:")
            bot.register_next_step_handler(msg, process_group_students)
            return

        group_id = add_group(group_name)
        if group_id:
            saved_count = add_batch_students(group_id, students_list)
            exam_id = user_exam_process[telegram_id].get("exam_id")
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            groups = get_all_groups()
            if groups:
                for g_id, g_name in groups:
                    markup.add(types.InlineKeyboardButton(f"👥 {g_name}", callback_data=f"select_group_{g_id}"))
            
            markup.add(types.InlineKeyboardButton("➕ Yangi guruh qo'shish", callback_data="add_new_group"))
            if exam_id:
                markup.add(types.InlineKeyboardButton("🔙 Ortga", callback_data=f"exam_detail_{exam_id}"))

            bot.send_message(
                message.chat.id,
                f"🎉 <b>{group_name}</b> muvaffaqiyatli yaratildi va {saved_count} ta talaba qo'shildi!\n\n"
                f"👥 <b>Imtihon olinadigan guruhni tanlang:</b>",
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            bot.send_message(message.chat.id, "❌ Guruh yaratishda xatolik yuz berdi (bunday guruh mavjud bo'lishi mumkin).")

    # --- GURUH TANLANGANDA 5 TALIK NAVBATni BOSHLASH ---
    @bot.callback_query_handler(func=lambda call: call.data.startswith("select_group_"))
    def handle_select_group_click(call):
        group_id = int(call.data.split("_")[2])
        telegram_id = call.from_user.id
        
        if telegram_id not in user_exam_process or "exam_id" not in user_exam_process[telegram_id]:
            bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.", show_alert=True)
            return
            
        exam_id = user_exam_process[telegram_id]["exam_id"]
        user_exam_process[telegram_id]["group_id"] = group_id

        # 5 talik batch navbatni yaratish (dublikat chaqiruv olib tashlandi)
        queue_result = start_exam_queue_batch(exam_id, group_id)
        
        if queue_result == "not_enough_questions":
            bot.answer_callback_query(call.id, "❌ Imtihonda kamida 3 ta savol bo'lishi kerak!", show_alert=True)
            return
            
        if not queue_result:
            bot.answer_callback_query(call.id, "❌ Guruhda talabalar topilmadi yoki barchasi qo'shilgan!", show_alert=True)
            return

        # O'qituvchiga dastlabki talabalar va kodlarni ko'rsatamiz
        text = "🎯 <b>Imtihon navbati shakllantirildi!</b>\n\n" \
               "Talabalar uchun maxsus kirish kodlari:\n\n"
               
        for item in queue_result:
            text += f"👤 <b>{item['name']}</b>\n🔑 Kod: <code>{item['code']}</code>\n\n"
            
        text += "Talabalar o'z kodlarini botga yuborib, savollarni olishlari mumkin."

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Keyingi talabalarni chiqarish", callback_data=f"next_queue_{exam_id}_{group_id}"))
        markup.add(types.InlineKeyboardButton("🎯 Tayyor talabani tekshirish", callback_data="check_ready_student"))
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data=f"start_exam_{exam_id}"))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=markup,
            parse_mode="HTML"
        )      

    # --- TAYYOR TALABANI TEKSHIRISH VA BAHOLASH ---
    @bot.callback_query_handler(func=lambda call: call.data == "check_ready_student")
    def check_ready_student_callback(call):
        teacher_telegram_id = call.from_user.id
        bot.answer_callback_query(call.id)
        
        ready_student = get_ready_students_for_teacher(teacher_telegram_id)
        
        if not ready_student:
            bot.answer_callback_query(call.id, "⚠️ Hozircha tayyor turgan talaba yo'q.", show_alert=True)
            return
            
        queue_id, student_name, q_texts, exam_id, group_id, student_id = ready_student
        
        # Savollarni qatorlarga ajratib olamiz
        questions_list = q_texts.split("\n")
        
        teacher_grading_states[teacher_telegram_id] = {
            "queue_id": queue_id,
            "exam_id": exam_id,
            "group_id": group_id,
            "student_id": student_id,
            "student_name": student_name,
            "questions_list": questions_list,
            "current_q_index": 0,
            "scores": []
        }
        
        # 1-savolni chiqaramiz
        markup = types.InlineKeyboardMarkup(row_width=5)
        markup.add(*(types.InlineKeyboardButton(str(i), callback_data=f"grade_score_{i}") for i in range(1, 6)))
        
        bot.send_message(
            call.message.chat.id,
            f"🎯 <b>Imtihon topshirilmoqda:</b>\n"
            f"👤 Talaba: <b>{student_name}</b>\n\n"
            f"📝 <b>1-savol:</b>\n{questions_list[0]}\n\n"
            f"⭐ <b>Bahoni tanlang:</b>",
            reply_markup=markup,
            parse_mode="HTML"
        )

    # Ball bosilganda dinamik ravishda keyingi savolga o'tish
    @bot.callback_query_handler(func=lambda call: call.data.startswith("grade_score_"))
    def grade_score_callback(call):
        teacher_telegram_id = call.from_user.id
        score = int(call.data.split("_")[2])
        bot.answer_callback_query(call.id)
        
        if teacher_telegram_id not in teacher_grading_states:
            bot.answer_callback_query(call.id, "⚠️ Seans eskirgan yoki yakunlangan.", show_alert=True)
            return
            
        state = teacher_grading_states[teacher_telegram_id]
        state["scores"].append(score)
        state["current_q_index"] += 1
        
        q_index = state["current_q_index"]
        questions_list = state["questions_list"]
        
        if q_index < len(questions_list):
            # Hali savollar bor, keyingi savolni chiqaramiz
            markup = types.InlineKeyboardMarkup(row_width=5)
            markup.add(*(types.InlineKeyboardButton(str(i), callback_data=f"grade_score_{i}") for i in range(1, 6)))
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"⭐ <b>{q_index}-savol uchun qo'yildi:</b> {score} ball\n\n"
                     f"📝 <b>{q_index + 1}-savol:</b>\n{questions_list[q_index]}\n\n"
                     f"⭐ <b>Bahoni tanlang:</b>",
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            # Barcha 3 ta savol baholandi, natijani saqlaymiz
            scores = state["scores"]
            queue_id = state["queue_id"]
            exam_id = state["exam_id"]
            group_id = state["group_id"]
            student_id = state["student_id"]
            student_name = state["student_name"]
            
            avg_score = save_exam_result(
                exam_id=exam_id,
                group_id=group_id,
                student_id=student_id,
                student_name=student_name,
                q1_text=questions_list[0], q1_score=scores[0],
                q2_text=questions_list[1], q2_score=scores[1],
                q3_text=questions_list[2], q3_score=scores[2]
            )
            
            # Navbatdagi talabani finished qilamiz
            finish_queue_item(queue_id)
            
            # Talabaning telegram_id sini topib natijani yuboramiz
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT student_telegram_id FROM exam_queue WHERE id = %s", (queue_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            
            if row and row[0]:
                student_tg_id = row[0]
                try:
                    bot.send_message(
                        student_tg_id,
                        f"🎉 <b>Imtihoningiz yakunlandi!</b>\n\n"
                        f"📊 Sizning baholaringiz:\n"
                        f"• 1-savol: {scores[0]} ball\n"
                        f"• 2-savol: {scores[1]} ball\n"
                        f"• 3-savol: {scores[2]} ball\n\n"
                        f"⭐ <b>O'rtacha ball: {avg_score}</b>",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"Talabaga xabar yuborishda xatolik: {e}")

            # Guruhdan KEYINGI TALABANI AVTO NAVBATGA QO'SHISH
            next_student_info = add_next_student_to_queue(exam_id, group_id)
            next_info_text = ""
            if next_student_info:
                next_info_text = f"\n\n➕ <b>Navbatga qo'shilgan keyingi talaba:</b>\n👤 {next_student_info['name']}\n🔑 Kod: <code>{next_student_info['code']}</code>"

            teacher_grading_states.pop(teacher_telegram_id, None)
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ <b>Imtihon yakunlandi va natija talabaga yuborildi!</b>\n\n"
                     f"👤 Talaba: <b>{student_name}</b>\n"
                     f"⭐ O'rtacha ball: <b>{avg_score}</b>"
                     f"{next_info_text}",
                parse_mode="HTML"
            )